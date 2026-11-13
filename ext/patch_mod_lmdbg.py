p = r'C:\Users\HENRIQUE\Tools\re1mod\mod\mod.c'
s = open(p, 'rb').read().decode('latin1').replace('\r\n', '\n')
def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)
rep(r'''float3 c=t.rgb*L*(i.c.a>0.5?1.0:2.0)*LOOK.z;\n"''',
    r'''float3 c=t.rgb*L*(i.c.a>0.5?1.0:2.0)*LOOK.z; if(LM.z>1.5) c=t.rgb; else if(LM.z>0.5) c=L;\n"''')
rep('static int g_lmMip = 1;', 'static int g_lmDbg = 0; /* ctl lmdbg 1 = lightmap only, 2 = albedo only */\nstatic int g_lmMip = 1;')
rep('        else if (sscanf(line, "lmmip %f", &a) == 1) g_lmMip = (int)a;', '        else if (sscanf(line, "lmmip %f", &a) == 1) g_lmMip = (int)a;\n        else if (sscanf(line, "lmdbg %f", &a) == 1) g_lmDbg = (int)a;')
rep('float lm[4] = { g_lmAmb, g_lmTone, 0, 0 };', 'float lm[4] = { g_lmAmb, g_lmTone, (float)g_lmDbg, 0 };')
open(p, 'wb').write(s.replace('\n', '\r\n').encode('latin1'))
print('patched')
