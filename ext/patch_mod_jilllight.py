# Scale the colour of the game's character point lights (sLightParam: [pos,1][dir][rgb,1][atten,1]) so our probe ambient
# can dominate. ctl: jilllight <k> (1 = game's own).
p = r'C:\Users\HENRIQUE\Tools\re1mod\mod\mod.c'
s = open(p, 'rb').read().decode('latin1').replace('\r\n', '\n')
def rep(a, b):
    global s
    assert a in s, a[:80]
    s = s.replace(a, b, 1)
rep('static float g_jillSH = 1.0f,', 'static float g_jillLight = 1.0f;\nstatic float g_jillSH = 1.0f,')
rep('    if (g_shOK && g_on && g_rms3 == 4 && !g_inRender && data && count == 7) return o_SetPixelShaderConstantF(d, start, g_sh7, 7);',
    '''    if (g_shOK && g_on && g_rms3 == 4 && !g_inRender && data && count == 7) return o_SetPixelShaderConstantF(d, start, g_sh7, 7);
    if (g_jillLight != 1.0f && g_on && g_rms3 == 4 && !g_inRender && data && count == 4 && data[3] == 1.0f && data[11] == 1.0f && data[15] == 1.0f) {
        float t[16]; memcpy(t, data, sizeof t); t[8] *= g_jillLight; t[9] *= g_jillLight; t[10] *= g_jillLight;
        return o_SetPixelShaderConstantF(d, start, t, 4);
    }''')
rep('        else if (sscanf(line, "jillsh %f", &a) == 1) g_jillSH = a;',
    '        else if (sscanf(line, "jillsh %f", &a) == 1) g_jillSH = a;\n        else if (sscanf(line, "jilllight %f", &a) == 1) g_jillLight = a;')
open(p, 'wb').write(s.replace('\n', '\r\n').encode('latin1'))
print('patched')
