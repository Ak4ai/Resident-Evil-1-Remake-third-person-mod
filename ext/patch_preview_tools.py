D = r'C:\Users\HENRIQUE\Tools\re1mod\ext'
s = open(D + r'\bake_lm_layers.py').read()
s = s.replace("SIZE=4096; SAMPLES=192", "import os\nSIZE=int(os.environ.get('LM_SIZE','4096')); SAMPLES=int(os.environ.get('LM_SAMPLES','192'))")
s = s.replace("want=sys.argv[sys.argv.index('--')+1:] or list(GROUPS)",
              "for _n in ('lustre_W','lustre_E','lustre_alto','fill_leste','fundo_oeste','lua'):\n    GROUPS['t_'+_n]=(lambda n,_n=_n: n==_n)\nwant=sys.argv[sys.argv.index('--')+1:] or list(GROUPS)")
old = "r'C:\\Users\\HENRIQUE\\Tools\\re1mod\\lm_layers\\%s.npy'%layer"
assert old in s
s = s.replace(old, "(r'C:\\Users\\HENRIQUE\\Tools\\re1mod\\lm_layers\\%s.npy' if SIZE==4096 else r'C:\\Users\\HENRIQUE\\Tools\\re1mod\\lm_layers\\small_%s.npy')%layer")
open(D + r'\bake_lm_layers.py', 'w').write(s)

p = open(D + r'\preview_rms4.py').read()
a = "W = {'base': 1.0, 'lareira': 1.0, 'velas': 1.0, 'arandelas': 0.45}"
assert a in p
p = p.replace(a, "import os\nW = {k: float(v) for k, v in (x.split(':') for x in os.environ['LAYERS'].split(','))} if os.environ.get('LAYERS') else {'base': 1.0, 'lareira': 1.0, 'velas': 1.0, 'arandelas': 0.45}")
p = p.replace("fac = EXPO ** 2.2", "fac = 1.0 if LMONLY else EXPO ** 2.2")
p = p.replace("rms4%s_%s.png' % ('lm' if LMONLY else '', n)", "rms4%s%s_%s.png' % ('lm' if LMONLY else '', os.environ.get('TAG', ''), n)")
open(D + r'\preview_rms4.py', 'w').write(p)
print('ok')
