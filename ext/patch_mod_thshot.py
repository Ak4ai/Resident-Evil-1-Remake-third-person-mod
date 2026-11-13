# Log every game thunder (rising edge of the c45 signal) as "THUNDER f=..." and, when armed with ctl "trovaoshot N",
# save 3 full-res frames at that moment (captures/sw777_*.bmp) plus 1 frame half a second later (sw778_*).
p = r'C:\Users\HENRIQUE\Tools\re1mod\mod\mod.c'
s = open(p, 'rb').read().decode('latin1').replace('\r\n', '\n')
def rep(a, b):
    global s
    assert a in s, a[:80]
    s = s.replace(a, b, 1)
rep('static float g_c45Max, g_gameFlash,', 'static int g_thArm, g_thLater;\nstatic float g_c45Max, g_gameFlash,')
rep('    { float f = (g_c45Max - 1.0f) / 0.7f; g_gameFlash = f < 0 ? 0 : f > 1.5f ? 1.5f : f; g_c45Max = 0; }\n',
    '''    { static float prev; float f = (g_c45Max - 1.0f) / 0.7f; g_gameFlash = f < 0 ? 0 : f > 1.5f ? 1.5f : f; g_c45Max = 0;
      if (g_gameFlash > 0.5f && prev <= 0.5f) { static int lastF; if (g_frames - lastF > 90) { M_("THUNDER f=%d\\n", g_frames); if (g_thArm) { g_shots = 3; g_swId = 777; g_shotK = 0; g_thLater = 30; g_thArm = 0; } } lastF = g_frames; }
      prev = g_gameFlash;
      if (g_thLater > 0 && --g_thLater == 0) { g_shots = 1; g_swId = 778; g_shotK = 0; } }
''')
rep('        else if (sscanf(line, "trovaomodo %f", &a) == 1) g_thMode = (int)a;',
    '''        else if (sscanf(line, "trovaomodo %f", &a) == 1) g_thMode = (int)a;
        else if (sscanf(line, "trovaoshot %f", &a) == 1) { static int lastA; if ((int)a != lastA) { lastA = (int)a; g_thArm = (int)a != 0; } }''')
open(p, 'wb').write(s.replace('\n', '\r\n').encode('latin1'))
print('patched')
