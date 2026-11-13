# Lightning also lifts the exposure of the whole room during the flash. ctl: trovaoexpo <k> (expo * (1 + flash*k)).
p = r'C:\Users\HENRIQUE\Tools\re1mod\mod\mod.c'
s = open(p, 'rb').read().decode('latin1').replace('\r\n', '\n')
def rep(a, b):
    global s
    assert a in s, a[:80]
    s = s.replace(a, b, 1)
rep('static float g_thunder = 1.0f,', 'static float g_thExpo = 1.2f;\nstatic float g_thunder = 1.0f,')
rep('        else if (sscanf(line, "trovaoamb %f", &a) == 1) g_thAmb = a;',
    '        else if (sscanf(line, "trovaoamb %f", &a) == 1) g_thAmb = a;\n        else if (sscanf(line, "trovaoexpo %f", &a) == 1) g_thExpo = a;')
rep('            IDirect3DDevice9_SetPixelShaderConstantF(dev, 0, g_look, 1); IDirect3DDevice9_SetPixelShaderConstantF(dev, 1, rt, 1);',
    '            float lk[4] = { g_look[0], g_look[1], g_look[2] * (1.0f + g_flash * g_thExpo), g_look[3] };\n            IDirect3DDevice9_SetPixelShaderConstantF(dev, 0, lk, 1); IDirect3DDevice9_SetPixelShaderConstantF(dev, 1, rt, 1);')
open(p, 'wb').write(s.replace('\n', '\r\n').encode('latin1'))
print('patched')
