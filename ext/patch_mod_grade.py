# RMS4 shader: flame/emissive gain + colour grade (warm tint and contrast), live from ctl.txt:
#   lmemis <gain>  (emissive parts, default 1)   tintr <mult>  tintb <mult>  (default 1)   contraste <gamma> (default 1; >1 = darker mids)
p = r'C:\Users\HENRIQUE\Tools\re1mod\mod\mod.c'
s = open(p, 'rb').read().decode('latin1').replace('\r\n', '\n')
def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)
rep(r'''    "float4 LM : register(c4);\n"''', r'''    "float4 LM : register(c4);\n"
    "float4 GR : register(c5);\n"''')
i = s.index('float4 psc4(VO4 i, float2 vp:VPOS):COLOR0{')
a = r'''float3 L=i.c.a>0.5 ? lm4(i.lm) : i.c.rgb;'''
j = s.index(a, i)
s = s[:j] + r'''float3 L=i.c.a>0.5 ? lm4(i.lm) : i.c.rgb*GR.x;''' + s[j + len(a):]
a = r'''c=lerp(l.xxx,c,LOOK.x);\n"'''
j = s.index(a, i)
s = s[:j] + r'''c=lerp(l.xxx,c,LOOK.x); c*=float3(GR.y,1.0,GR.z); c=pow(max(c,0.0),GR.w);\n"''' + s[j + len(a):]
rep('static float g_lmClip = 0.5f;', 'static float g_grade[4] = { 1, 1, 1, 1 }; /* ctl lmemis, tintr, tintb, contraste */\nstatic float g_lmClip = 0.5f;')
rep('        else if (sscanf(line, "lmclip %f", &a) == 1) g_lmClip = a;',
    '''        else if (sscanf(line, "lmclip %f", &a) == 1) g_lmClip = a;
        else if (sscanf(line, "lmemis %f", &a) == 1) g_grade[0] = a;
        else if (sscanf(line, "tintr %f", &a) == 1) g_grade[1] = a;
        else if (sscanf(line, "tintb %f", &a) == 1) g_grade[2] = a;
        else if (sscanf(line, "contraste %f", &a) == 1) g_grade[3] = a;''')
rep('IDirect3DDevice9_SetPixelShaderConstantF(dev, 4, lm, 1); }', 'IDirect3DDevice9_SetPixelShaderConstantF(dev, 4, lm, 1); IDirect3DDevice9_SetPixelShaderConstantF(dev, 5, g_grade, 1); }')
open(p, 'wb').write(s.replace('\n', '\r\n').encode('latin1'))
print('patched')
