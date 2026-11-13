# ctl "shot N": save the next N back buffers at full resolution (captures/sw<id>_<k>.bmp) for close inspection.
p = r'C:\Users\HENRIQUE\Tools\re1mod\mod\mod.c'
s = open(p, 'rb').read().decode('latin1').replace('\r\n', '\n')
a = '        else if (sscanf(line, "gamecam %f", &a) == 1) { if (a != 0) g_haveCam = 0; }'
assert a in s
s = s.replace(a, a + '\n        else if (sscanf(line, "shot %f", &a) == 1) { static int last; if ((int)a != last) { g_shots = (int)a; g_swId = 900 + (int)a; g_shotK = 0; last = (int)a; } }', 1)
# g_shots is declared after read_ctl: move a forward declaration up
s = s.replace('static float g_halo = 1.0f,', 'static int g_shots, g_swId, g_shotK;\nstatic float g_halo = 1.0f,', 1)
s = s.replace('static int g_shots, g_nSwShots, g_swId, g_shotK; /*', 'static int g_nSwShots; /*', 1)
open(p, 'wb').write(s.replace('\n', '\r\n').encode('latin1'))
print('patched')
