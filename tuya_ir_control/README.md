# Tuya IR Control 0.3.2

Home Assistant App com Ingress. Gerencia controles Tuya existentes e controles personalizados separados.

## Recursos 0.3.x
- Interface web dentro da página do App (Ingress).
- Controles Tuya existentes separados de controles personalizados.
- Criação de controles personalizados.
- Captura IR com polling automático.
- Exibição imediata do código capturado.
- Teste antes de salvar.
- Nome personalizado para cada tecla.
- Recaptura, teste, renomeação e exclusão de teclas.
- Dados personalizados persistidos em `/data/custom_controls.json`.

> Controles personalizados usam um `remote_id` Tuya existente como transporte para retransmitir o código aprendido. A interface escolhe um controle-base ao criar o controle personalizado.
