# Characters lit by OUR room: the game's character shaders take their ambient from fSHCoef (7 regs, Unity-style packing:
# cAr cAg cAb = (x, y, z, const), cBr cBg cBb = (xy, yz, zz, zx), cC = (x2-y2 for r,g,b)). We replace every 7-register pixel
# constant write with the ambient interpolated from captures/r105_probes.bin (ext/probes_build.py) at Jill's position,
# mixing the 4 light layers with the same flicker/weights as the room. ctl: jillsh <scale> (0 = game's own), jillalt <cm>.
p = r'C:\Users\HENRIQUE\Tools\re1mod\mod\mod.c'
s = open(p, 'rb').read().decode('latin1').replace('\r\n', '\n')
def rep(a, b):
    global s
    assert a in s, a[:80]
    s = s.replace(a, b, 1)

rep('static int g_thArm, g_thLater;', '''static int g_thArm, g_thLater;
static float *g_probe; static int g_pn[3]; static float g_p0[3], g_pst[3]; static float g_jillSH = 1.0f, g_jillAlt = 110.0f, g_sh7[28]; static int g_shOK;''')
# load next to the halos
rep('        M_("halos %d spec lights %d\\n", g_nHalo, g_nSpecL);',
    '''        M_("halos %d spec lights %d\\n", g_nHalo, g_nSpecL);
        {   char pp[MAX_PATH]; FILE *pf; int hd[3]; float f4[4], st[3];
            snprintf(pp, sizeof pp, "%s\\\\r105_probes.bin", dir); pf = fopen(pp, "rb");
            if (pf && fread(hd, 4, 3, pf) == 3 && fread(f4, 4, 4, pf) == 4 && fread(st, 4, 3, pf) == 3 && hd[0] > 1 && hd[1] > 1 && hd[2] > 1 && hd[0] * hd[1] * hd[2] < 100000) {
                size_t n = (size_t)hd[0] * hd[1] * hd[2] * 108;
                free(g_probe); g_probe = (float *)malloc(n * 4);
                if (g_probe && fread(g_probe, 4, n, pf) == n) { memcpy(g_pn, hd, 12); memcpy(g_p0, f4, 12); memcpy(g_pst, st, 12); M_("probes %dx%dx%d\\n", hd[0], hd[1], hd[2]); }
                else { free(g_probe); g_probe = NULL; }
            }
            if (pf) fclose(pf);
        }''')
# per-frame ambient at the player
rep('static void update_flash(void)\n{', r'''static int read_player(float *pos, float *fwd);
static void update_jill_sh(void)
{
    float p[3], f[3], b[3], fi[3], acc[3][9]; int i0[3], k, l, ch, t, ix, iy, iz;
    g_shOK = 0;
    if (!g_probe || g_jillSH <= 0 || !read_player(p, f)) return;
    b[0] = p[0] / 100.0f; b[1] = p[2] / 100.0f; b[2] = (p[1] + g_jillAlt) / 100.0f;      /* game (x, y-up, z) -> blender (x, z, y) */
    for (k = 0; k < 3; k++) { float u = (b[k] - g_p0[k]) / g_pst[k]; if (u < 0) u = 0; if (u > g_pn[k] - 1.001f) u = g_pn[k] - 1.001f; i0[k] = (int)u; fi[k] = u - i0[k]; }
    memset(acc, 0, sizeof acc);
    for (t = 0; t < 8; t++) {
        float w = ((t & 1) ? fi[0] : 1 - fi[0]) * ((t & 2) ? fi[1] : 1 - fi[1]) * ((t & 4) ? fi[2] : 1 - fi[2]);
        ix = i0[0] + (t & 1); iy = i0[1] + ((t >> 1) & 1); iz = i0[2] + ((t >> 2) & 1);
        { const float *pr = g_probe + (((size_t)ix * g_pn[1] + iy) * g_pn[2] + iz) * 108;
          for (l = 0; l < 4; l++) { float lw = w * g_flick[l] * g_lmW[l];
              for (ch = 0; ch < 3; ch++) for (k = 0; k < 9; k++) acc[ch][k] += lw * pr[(l * 3 + ch) * 9 + k]; } }
    }
    for (ch = 0; ch < 3; ch++) {
        float *A = g_sh7 + ch * 4, *Bv = g_sh7 + 12 + ch * 4, sc = g_jillSH;
        A[0] = acc[ch][1] * sc; A[1] = acc[ch][2] * sc; A[2] = acc[ch][3] * sc; A[3] = acc[ch][0] * sc;
        Bv[0] = acc[ch][4] * sc; Bv[1] = acc[ch][5] * sc; Bv[2] = acc[ch][6] * sc; Bv[3] = acc[ch][7] * sc;
        g_sh7[24 + ch] = acc[ch][8] * sc;
    }
    g_sh7[27] = 1.0f; g_shOK = 1;
}
static void update_flash(void)
{''')
rep('    update_flash();\n', '    update_flash();\n    update_jill_sh();\n')
rep('''    if (!g_inRender && data && start <= 45 && start + count > 45) {''',
    '''    if (g_shOK && g_on && g_rms3 == 4 && !g_inRender && data && count == 7) return o_SetPixelShaderConstantF(d, start, g_sh7, 7);
    if (!g_inRender && data && start <= 45 && start + count > 45) {''')
rep('        else if (sscanf(line, "trovaomodo %f", &a) == 1) g_thMode = (int)a;',
    '''        else if (sscanf(line, "trovaomodo %f", &a) == 1) g_thMode = (int)a;
        else if (sscanf(line, "jillsh %f", &a) == 1) g_jillSH = a;
        else if (sscanf(line, "jillalt %f", &a) == 1) g_jillAlt = a;''')
open(p, 'wb').write(s.replace('\n', '\r\n').encode('latin1'))
print('patched')
