p = r'C:\Users\HENRIQUE\Tools\re1mod\mod\mod.c'
s = open(p, 'rb').read().decode('latin1').replace('\r\n', '\n')
def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)
rep('static float g_lmAmb = 0.08f,', 'static int g_lmMip = 1; /* ctl lmmip 0 = lightmap without mipmaps */\nstatic float g_lmAmb = 0.08f,')
rep('        else if (sscanf(line, "lmamb %f", &a) == 1) g_lmAmb = a;', '        else if (sscanf(line, "lmamb %f", &a) == 1) g_lmAmb = a;\n        else if (sscanf(line, "lmmip %f", &a) == 1) g_lmMip = (int)a;')
rep('IDirect3DDevice9_SetSamplerState(dev, 1 + li, D3DSAMP_MIPFILTER, D3DTEXF_LINEAR);', 'IDirect3DDevice9_SetSamplerState(dev, 1 + li, D3DSAMP_MIPFILTER, g_lmMip ? D3DTEXF_LINEAR : D3DTEXF_NONE);')
open(p, 'wb').write(s.replace('\n', '\r\n').encode('latin1'))
print('patched')
