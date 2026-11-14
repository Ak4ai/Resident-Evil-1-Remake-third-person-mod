@echo off
rem Bake completo da madrugada (UV v3 corrigido + porta + relampago/luar), limpeza, PNG com alfa e instalacao no jogo.
rem Progresso em noite.log; detalhes em logs_noite_*.txt. Backup do que estava instalado em captures\bak_pre_noite\.
cd /d C:\Users\HENRIQUE\Tools\re1mod
set BL="C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
set CAP=C:\Users\HENRIQUE\Tools\captures
echo [1] bake 6 camadas %date% %time% > noite.log
set LM_SAMPLES=128
%BL% -b blend\r105_lm_v3.blend --python ext\bake_lm_layers.py -- base lareira velas arandelas relampago luar > logs_noite_bake.txt 2>&1
findstr /C:"LAYER" logs_noite_bake.txt >> noite.log
for /f %%n in ('findstr /C:"LAYER" logs_noite_bake.txt ^| %SystemRoot%System32ind.exe /c /v ""') do set NL=%%n
if not "%NL%"=="6" (echo ERRO: bake terminou com %NL% de 6 camadas, nada foi instalado %date% %time% >> noite.log & exit /b 1)
echo [2] limpeza %date% %time% >> noite.log
python ext\despeckle_lm.py base lareira velas arandelas relampago luar > logs_noite_post.txt 2>&1
python ext\dilate_lm.py base lareira velas arandelas relampago luar >> logs_noite_post.txt 2>&1
echo [3] backup do instalado %date% %time% >> noite.log
if not exist %CAP%\bak_pre_noite mkdir %CAP%\bak_pre_noite
copy /y %CAP%\r105.rms2 %CAP%\bak_pre_noite\ >nul
copy /y %CAP%\r105_lm_*.png %CAP%\bak_pre_noite\ >nul
echo [4] PNG com alfa %date% %time% >> noite.log
python ext\lm_layers_to_png.py >> logs_noite_post.txt 2>&1
echo [5] instala %date% %time% >> noite.log
copy /y %CAP%\r105_lm.rms4 %CAP%\r105.rms2 >nul
echo FIM %date% %time% >> noite.log
