# Lightning: random strikes (double flash) brighten the window landscape, boost the moonlight shafts (whiter) and lift the
# room ambient a little. ctl: trovao <strength> (0 = off), trovaoint <min s> <max s>, trovaoamb <ambient add>, trovaoteste 1 (strike now).
p = r'C:\Users\HENRIQUE\Tools\re1mod\mod\mod.c'
s = open(p, 'rb').read().decode('latin1').replace('\r\n', '\n')
def rep(a, b):
    global s
    assert a in s, a[:80]
    s = s.replace(a, b, 1)

rep('static float g_sharp = 0.0f,', '''static float g_thunder = 1.0f, g_thMin = 9.0f, g_thMax = 26.0f, g_thAmb = 0.05f, g_flash; static int g_thTest; /* ctl trovao, trovaoint, trovaoamb, trovaoteste */
/* lightning envelope: a main flash and 1-2 flickers, ~0.7 s, at random intervals */
static void update_flash(void)
{
    static double next = 0, start = -100; static int seeded; static float k2, k3;
    double t = GetTickCount() * 0.001; float f = 0, dt;
    if (!seeded) { srand(GetTickCount()); next = t + 4.0; seeded = 1; }
    if (g_thunder <= 0) { g_flash = 0; return; }
    if (g_thTest) { next = t; g_thTest = 0; }
    if (t >= next) { start = t; next = t + g_thMin + (g_thMax - g_thMin) * (rand() / (float)RAND_MAX); k2 = 0.5f + 0.5f * (rand() / (float)RAND_MAX); k3 = (rand() & 1) ? 0.6f : 0.0f; }
    dt = (float)(t - start);
    if (dt >= 0 && dt < 1.2f) {
        if (dt < 0.04f) f = dt / 0.04f; else f = expf(-(dt - 0.04f) / 0.09f);
        if (dt > 0.18f) f = fmaxf(f, k2 * expf(-fabsf(dt - 0.24f) / 0.05f));
        if (dt > 0.45f) f = fmaxf(f, k3 * expf(-fabsf(dt - 0.52f) / 0.06f));
    }
    g_flash = f * g_thunder;
}
static float g_sharp = 0.0f,''')
rep('        else if (sscanf(line, "grao %f", &a) == 1) g_grain = a;',
    '''        else if (sscanf(line, "grao %f", &a) == 1) g_grain = a;
        else if (sscanf(line, "trovaoint %f %f", &a, &b) == 2) { g_thMin = a; g_thMax = b > a ? b : a + 1; }
        else if (sscanf(line, "trovaoamb %f", &a) == 1) g_thAmb = a;
        else if (sscanf(line, "trovaoteste %f", &a) == 1) { static int lastT; if ((int)a != lastT) { g_thTest = (int)a != 0; lastT = (int)a; } }
        else if (sscanf(line, "trovao %f", &a) == 1) g_thunder = a;''')
# shader: landscape parts get brighter with the flash (GL.y = flash for the landscape part, 0 otherwise)
i = s.index('float4 psc4(VO4 i, float2 vp:VPOS):COLOR0{')
a = r'''float3 sp=spec4(i.wp); if(LM.z<0.5) c+=sp;\n"'''
j = s.index(a, i)
s = s[:j] + r'''float3 sp=spec4(i.wp); if(LM.z<0.5) c+=sp; c*=1.0+GL.y*float3(2.6,2.9,3.4);\n"''' + s[j + len(a):]
rep('                float gl[4] = { 0, 0, 0, 0 };', '                float gl[4] = { 0, strstr(pt->name, "paisagem_noite") ? g_flash : 0.0f, 0, 0 };')
# ambient lift
rep('{ float lm[4] = { g_lmAmb, g_lmTone, (float)g_lmDbg, g_lmClip };', '{ float lm[4] = { g_lmAmb + g_flash * g_thAmb, g_lmTone, (float)g_lmDbg, g_lmClip };')
# shafts: stronger and whiter while flashing
rep('ld[3] = g_vol * 0.0012f;', 'ld[3] = g_vol * 0.0012f * (1.0f + 3.5f * g_flash);')
rep('float col[4] = { g_volCol[0], g_volCol[1], g_volCol[2], 1800.0f },',
    'float wf = g_flash > 1 ? 1 : g_flash, col[4] = { g_volCol[0] + (0.85f - g_volCol[0]) * wf, g_volCol[1] + (0.88f - g_volCol[1]) * wf, g_volCol[2] + (0.95f - g_volCol[2]) * wf, 1800.0f },')
# update once per frame, before drawing
rep('    if (!(g_nparts > 0 || (g_vb && g_ib && g_psc))) return;\n    if (g_bis & 4) return;\n    g_inRender = 1;',
    '    if (!(g_nparts > 0 || (g_vb && g_ib && g_psc))) return;\n    if (g_bis & 4) return;\n    g_inRender = 1;\n    update_flash();')
open(p, 'wb').write(s.replace('\n', '\r\n').encode('latin1'))
print('patched')
