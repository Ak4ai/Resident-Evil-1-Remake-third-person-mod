# Follow the GAME's own lightning: during the original thunder the game writes 1.7 (instead of 1.0) to pixel-shader
# constant c45 (with c39/c43/c44 = 554 and c53 = 500), flickering frame by frame for ~1 s. We read that per frame and drive
# our flash (window, shafts, room exposure) from it, so it lights up exactly when Jill does.
# ctl: trovaomodo 1 = follow the game (default), 0 = our own random strikes; trovaosuave <s> = decay to soften the strobe.
p = r'C:\Users\HENRIQUE\Tools\re1mod\mod\mod.c'
s = open(p, 'rb').read().decode('latin1').replace('\r\n', '\n')
def rep(a, b):
    global s
    assert a in s, a[:80]
    s = s.replace(a, b, 1)
rep('static float g_psMax[64];', 'static float g_c45Max, g_gameFlash, g_thSmooth = 0.06f; static int g_thMode = 1;\nstatic float g_psMax[64];')
rep('''    if (g_psRec > 0 && !g_inRender && data) {''', '''    if (!g_inRender && data && start <= 45 && start + count > 45) { float v = data[(45 - start) * 4]; if (v > g_c45Max) g_c45Max = v; }
    if (g_psRec > 0 && !g_inRender && data) {''')
rep('    if (g_frames % 10 == 0) read_ctl();\n',
    '    if (g_frames % 10 == 0) read_ctl();\n    { float f = (g_c45Max - 1.0f) / 0.7f; g_gameFlash = f < 0 ? 0 : f > 1.5f ? 1.5f : f; g_c45Max = 0; }\n')
rep('        else if (sscanf(line, "trovaoexpo %f", &a) == 1) g_thExpo = a;',
    '''        else if (sscanf(line, "trovaoexpo %f", &a) == 1) g_thExpo = a;
        else if (sscanf(line, "trovaomodo %f", &a) == 1) g_thMode = (int)a;
        else if (sscanf(line, "trovaosuave %f", &a) == 1) g_thSmooth = a;''')
rep('''    if (g_thunder <= 0) { g_flash = 0; return; }''', '''    if (g_thunder <= 0) { g_flash = 0; return; }
    if (g_thMode == 1) {   /* follow the game's thunder light (c45), with a short decay so the per-frame strobe reads as a flash */
        static double lt; static float cur; float dtf = lt > 0 ? (float)(t - lt) : 0.016f; lt = t;
        if (g_gameFlash >= cur) cur = g_gameFlash; else cur = g_gameFlash + (cur - g_gameFlash) * (g_thSmooth > 0 ? expf(-dtf / g_thSmooth) : 0.0f);
        g_flash = cur * g_thunder; return;
    }''')
open(p, 'wb').write(s.replace('\n', '\r\n').encode('latin1'))
print('patched')
