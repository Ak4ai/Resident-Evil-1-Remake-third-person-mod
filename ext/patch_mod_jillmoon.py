# Jill inside a window beam gets the moonlight in her ambient (directional term from the moon direction).
# Same analytic beam test as the shafts (3 north windows, soft edges, fade along the beam). ctl: jillmoon <k> (0 = off).
p = r'C:\Users\HENRIQUE\Tools\re1mod\mod\mod.c'
s = open(p, 'rb').read().decode('latin1').replace('\r\n', '\n')
def rep(a, b):
    global s
    assert a in s, a[:80]
    s = s.replace(a, b, 1)
rep('static float g_jillLight = 1.0f;', '''static float g_jillLight = 1.0f, g_jillMoon = 1.0f;
static float g_volDir[3], g_volCol[3], g_vol, g_volFade, g_volSoft; /* tentative, defined below */
static float beam_cpu(float x, float y, float z)
{
    static const float cx[3] = { -525.0f, 8.0f, 540.0f }; const float hw = 68.0f, WZ = 382.0f, YB = 92.0f, YS = 205.0f;
    float n = sqrtf(g_volDir[0] * g_volDir[0] + g_volDir[1] * g_volDir[1] + g_volDir[2] * g_volDir[2]), L[3], t, qx, qy, best = 0, sw = g_volSoft > 1 ? g_volSoft : 1;
    int k;
    if (n < 1e-6f) return 0; L[0] = g_volDir[0] / n; L[1] = g_volDir[1] / n; L[2] = g_volDir[2] / n;
    if (z > WZ || L[2] > -0.05f) return 0;
    t = (WZ - z) / (-L[2]); qx = x - L[0] * t; qy = y - L[1] * t;
    for (k = 0; k < 3; k++) {
        float dx = fabsf(qx - cx[k]), dy = qy - YS, side, bot, top;
        side = (hw - dx) / sw; side = side < 0 ? 0 : side > 1 ? 1 : side;
        bot = (qy - YB) / sw; bot = bot < 0 ? 0 : bot > 1 ? 1 : bot;
        if (qy < YS) top = 1; else { top = (hw - sqrtf(dx * dx + dy * dy)) / sw; top = top < 0 ? 0 : top > 1 ? 1 : top; }
        if (side * bot * top > best) best = side * bot * top;
    }
    return best * expf(-t / (g_volFade > 10 ? g_volFade : 10));
}''')
rep('    for (ch = 0; ch < 3; ch++) {\n        float *A = g_sh7 + ch * 4,',
    '''    if (g_jillMoon > 0 && g_vol > 0) {
        float bm = beam_cpu(p[0], p[1] + g_jillAlt, p[2]), n = sqrtf(g_volDir[0] * g_volDir[0] + g_volDir[1] * g_volDir[1] + g_volDir[2] * g_volDir[2]);
        if (bm > 0.001f && n > 1e-6f) {
            float k = bm * g_jillMoon * g_vol * 0.004f * (1.0f + 3.0f * g_flash);
            for (ch = 0; ch < 3; ch++) { float C = g_volCol[ch] * k;
                acc[ch][0] += C * 0.25f; acc[ch][1] += C * 0.5f * (-g_volDir[0] / n); acc[ch][2] += C * 0.5f * (-g_volDir[1] / n); acc[ch][3] += C * 0.5f * (-g_volDir[2] / n); }
        }
    }
    for (ch = 0; ch < 3; ch++) {
        float *A = g_sh7 + ch * 4,''')
rep('        else if (sscanf(line, "jillsh %f", &a) == 1) g_jillSH = a;', '        else if (sscanf(line, "jillsh %f", &a) == 1) g_jillSH = a;\n        else if (sscanf(line, "jillmoon %f", &a) == 1) g_jillMoon = a;')
open(p, 'wb').write(s.replace('\n', '\r\n').encode('latin1'))
print('patched')
