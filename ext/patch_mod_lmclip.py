p = r'C:\Users\HENRIQUE\Tools\re1mod\mod\mod.c'
s = open(p, 'rb').read().decode('latin1').replace('\r\n', '\n')
def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)
# only the RMS4 pixel shader (psc4): the line right after the VO4 struct / psc4 header
i = s.index('float4 psc4(VO4 i, float2 vp:VPOS):COLOR0{')
j = s.index('clip(t.a-0.5);', i)
s = s[:j] + 'clip(t.a-LM.w);' + s[j + len('clip(t.a-0.5);'):]
rep('static int g_lmDbg = 0;', 'static float g_lmClip = 0.5f; /* ctl lmclip: alpha threshold of the RMS4 shader (0 = no alpha clip) */\nstatic int g_lmDbg = 0;')
rep('        else if (sscanf(line, "lmdbg %f", &a) == 1) g_lmDbg = (int)a;', '        else if (sscanf(line, "lmdbg %f", &a) == 1) g_lmDbg = (int)a;\n        else if (sscanf(line, "lmclip %f", &a) == 1) g_lmClip = a;')
rep('float lm[4] = { g_lmAmb, g_lmTone, (float)g_lmDbg, 0 };', 'float lm[4] = { g_lmAmb, g_lmTone, (float)g_lmDbg, g_lmClip };')
open(p, 'wb').write(s.replace('\n', '\r\n').encode('latin1'))
print('patched')
