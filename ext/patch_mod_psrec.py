# Diagnostic: per frame, the max |rgb| the GAME wrote to each pixel-shader constant register c0..c63 (our own render is
# excluded). ctl "psrec N" records N frames to captures/psrec.bin (64 floats per frame) to find the original thunder signal.
p = r'C:\Users\HENRIQUE\Tools\re1mod\mod\mod.c'
s = open(p, 'rb').read().decode('latin1').replace('\r\n', '\n')
def rep(a, b):
    global s
    assert a in s, a[:80]
    s = s.replace(a, b, 1)
rep('static float g_thExpo = 1.2f;', 'static float g_thExpo = 1.2f;\nstatic float g_psMax[64]; static int g_psRec; static FILE *g_psFile;')
rep('''HOOKFN(HRESULT, SetPixelShaderConstantF, UINT start, const float *data, UINT count)
{''', '''HOOKFN(HRESULT, SetPixelShaderConstantF, UINT start, const float *data, UINT count)
{
    if (g_psRec > 0 && !g_inRender && data) {
        UINT r; for (r = 0; r < count && start + r < 64; r++) {
            float m = fmaxf(fabsf(data[r * 4]), fmaxf(fabsf(data[r * 4 + 1]), fabsf(data[r * 4 + 2])));
            if (m > g_psMax[start + r]) g_psMax[start + r] = m; }
    }''')
rep('        else if (sscanf(line, "trovaoexpo %f", &a) == 1) g_thExpo = a;',
    '''        else if (sscanf(line, "trovaoexpo %f", &a) == 1) g_thExpo = a;
        else if (sscanf(line, "psrec %f", &a) == 1) { static int lastR; if ((int)a != lastR) { lastR = (int)a; g_psRec = (int)a;
            if (g_psFile) fclose(g_psFile); { char pp[MAX_PATH]; snprintf(pp, sizeof pp, "%s\\\\psrec.bin", g_dir); g_psFile = fopen(pp, "wb"); } memset(g_psMax, 0, sizeof g_psMax); } }''')
# once per frame: next to the periodic ctl read
rep('    if (g_frames % 10 == 0) read_ctl();',
    '''    if (g_frames % 10 == 0) read_ctl();
    if (g_psRec > 0 && g_psFile) { fwrite(g_psMax, sizeof g_psMax, 1, g_psFile); memset(g_psMax, 0, sizeof g_psMax);
        if (--g_psRec == 0) { fclose(g_psFile); g_psFile = NULL; M_("psrec done\\n"); } }''')
open(p, 'wb').write(s.replace('\n', '\r\n').encode('latin1'))
print('patched')
