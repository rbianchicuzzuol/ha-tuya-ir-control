## 0.3.4
- Corrige descoberta de Ar-condicionado usando o category_id oficial 5, sem depender do nome/localização retornado pela Tuya.
- Mantém o assistente AC por catálogo e normaliza o ID para os comandos de teste.

# Changelog

## 0.3.3
- Novo assistente dedicado para ar-condicionado via biblioteca Tuya: marca, índices, teste e vínculo.
- Ar-condicionado deixa de usar aprendizado bruto quando escolhido como tipo.
- Testes estruturados de Power, temperatura, modo e ventilação antes de adicionar.
- Tela dedicada para controles AC vinculados.
- DIY e demais controles aprendidos continuam separados e compatíveis com dados da 0.3.2.


## 0.3.2
- Corrige o botão Fechar dos modais (conflito com `window.close`).
- Controles personalizados agora são criados do zero, sem escolher um controle Tuya existente como base.
- Novo seletor de tipo: TV, Decodificador de TV, TV Box, Ar-condicionado, Ventilador, Luz, Áudio, Projetor, DVD, Câmera, Aquecedor, Purificador e DIY.
- DIY solicita o tipo de equipamento de referência.
- Após criar o controle, o aprendizado da primeira tecla inicia automaticamente.
- A primeira tecla aprendida cria um controle DIY real pela API `Save Learning Code` da Tuya; teclas seguintes usam `Update Learning Code`.
- Captura continua automática, mostra o código, permite testar e salvar.
- Fechamento por botão, clique fora do modal e tecla Esc.

## 0.3.1
- Corrige dependência aiohttp e build do App.
