# Mapa do projeto

*[English version](ROADMAP.md)*

## Feito

### Motor / mod
- [x] Carregador `d3d9.dll` e DLL do mod que recarrega com o jogo aberto
- [x] Câmera livre em terceira pessoa: segue, gira no analógico direito, distância segura contra paredes
- [x] Modo de mira por cima do ombro com retícula; a personagem vira para a câmera
- [x] Busca automática do nó da personagem na memória (sem Cheat Engine)
- [x] Ajuste ao vivo pelo `ctl.txt`
- [x] Formatos de sala RMS2 / RMS3 (luz por vértice) / RMS4 (lightmap)
- [x] Shader de lightmap com 4 camadas animadas (geral, lareira, velas, arandelas)
- [x] Bloom só nas fontes de luz, halos, granulado, correção de cor
- [x] Feixes volumétricos de luar pelas janelas
- [x] Grade de 800 sondas iluminando a personagem, mais o feixe de luar
- [x] Esconder as partículas 2D de fogo do jogo quando a sala 3D é desenhada

### Sala 105 (sala de jantar)
- [x] Reconstrução 3D conferida com os fundos e mapas de profundidade do jogo
- [x] Pilastras, cornijas, nichos, teto e painéis limpos
- [x] Luz assada no Blender/Cycles (OptiX)
- [x] UV do lightmap v3: faces finas (chanfros, molduras) alargadas, sem linhas pretas nas quinas
- [x] Verificador do modelo: z-fighting, faces escondidas, faces finas demais, renderizado nas câmeras do jogo
- [x] Z-fighting da lareira removido

## Em andamento
- [ ] Assar de novo as camadas de lareira, velas e arandelas no UV v3
- [ ] Camada de relâmpago: luz forte pelas janelas da parede norte no trovão, no canal alfa do lightmap base
- [ ] Camada de luar: manchas das janelas no chão, no canal alfa do lightmap da lareira
- [ ] Suporte no shader para as duas camadas das janelas

## A fazer
- [ ] Confirmar a detecção do trovão pelas constantes do shader do jogo
- [ ] Distribuição da luz igual aos fundos originais, câmera por câmera
- [ ] Objetos pequenos e detalhados (cadeiras, lustres, lanternas, estátuas) com luz por vértice em vez de lightmap
- [ ] Teste confiável de frestas no verificador
- [ ] Sombra da personagem pelas luzes da sala
- [ ] Caminhos configuráveis (sem pastas fixas do usuário)
- [ ] Pacote de release e guia de instalação
- [ ] Próximas salas
