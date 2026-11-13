# ctl "gamecam 1": every ctl read, drop the free-camera pose so the mod re-derives it from the game's current fixed camera
# (cam_from_matrix). With "follow 0" the mod then renders exactly the original camera framing (for A/B with "on 0").
p = r'C:\Users\HENRIQUE\Tools\re1mod\mod\mod.c'
s = open(p, 'rb').read().decode('latin1').replace('\r\n', '\n')
a = '        else if (sscanf(line, "lmemis %f", &a) == 1) g_grade[0] = a;'
assert a in s
s = s.replace(a, a + '\n        else if (sscanf(line, "gamecam %f", &a) == 1) { if (a != 0) g_haveCam = 0; }', 1)
open(p, 'wb').write(s.replace('\n', '\r\n').encode('latin1'))
print('patched')
