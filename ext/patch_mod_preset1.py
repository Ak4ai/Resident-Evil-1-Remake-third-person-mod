# Adds a fixed camera preset: with the camera detached (F11 -> follow=0), key '1' jumps to the preset pose.
# ctl.txt: "preset1 x y z yaw pitch fov". Current pose is also written to captures/pose.txt (x y z yaw pitch fov) every 15 frames.
p = r'C:\Users\HENRIQUE\Tools\re1mod\mod\mod.c'
s = open(p, 'rb').read().decode('latin1').replace('\r\n', '\n')
def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)
rep('static int g_lmDbg = 0;', 'static float g_pre1[6] = { -75.8f, 208.8f, 46.7f, 2.54f, -0.16f, 55.0f }; /* ctl preset1: central room camera (game units) */\nstatic int g_lmDbg = 0;')
rep('        else if (sscanf(line, "lmdbg %f", &a) == 1) g_lmDbg = (int)a;',
    '        else if (sscanf(line, "lmdbg %f", &a) == 1) g_lmDbg = (int)a;\n        else if (sscanf(line, "preset1 %f %f %f %f %f %f", &g_pre1[0], &g_pre1[1], &g_pre1[2], &g_pre1[3], &g_pre1[4], &g_pre1[5]) == 6) {}')
rep('    g_prevF10 = k; g_prevF11 = k2;',
    '''    g_prevF10 = k; g_prevF11 = k2;
    {
        static int prev1; int k1 = (GetAsyncKeyState('1') & 0x8000) != 0;
        if (k1 && !prev1 && g_on && !g_follow) {
            g_pos[0] = g_pre1[0]; g_pos[1] = g_pre1[1]; g_pos[2] = g_pre1[2]; g_yaw = g_pre1[3]; g_pitch = g_pre1[4]; g_fov = g_pre1[5]; g_haveCam = 1;
            M_("key 1 -> preset camera pos %.1f %.1f %.1f yaw %.2f pitch %.2f fov %.1f\\n", g_pos[0], g_pos[1], g_pos[2], g_yaw, g_pitch, g_fov);
        }
        prev1 = k1;
        if (g_haveCam && g_frames % 15 == 0) {
            char pp[MAX_PATH]; FILE *pf; snprintf(pp, sizeof pp, "%s\\\\pose.txt", g_dir); pf = fopen(pp, "w");
            if (pf) { fprintf(pf, "%.3f %.3f %.3f %.4f %.4f %.3f\\n", g_pos[0], g_pos[1], g_pos[2], g_yaw, g_pitch, g_fov); fclose(pf); }
        }
    }''')
open(p, 'wb').write(s.replace('\n', '\r\n').encode('latin1'))
print('patched')
