# Tuya IR Control 0.3.0 — Home Assistant App

Repositório para Home Assistant Apps (antigos add-ons) com interface via Ingress.

## Instalação
1. Publique todo este conteúdo na raiz de um repositório GitHub.
2. Edite `repository.yaml` e `tuya_ir_control/config.yaml`, trocando `SEU_USUARIO` pela URL real.
3. No Home Assistant: **Configurações → Aplicativos → Loja de aplicativos → ⋮ → Repositórios**.
4. Adicione a URL do repositório GitHub.
5. Instale **Tuya IR Control**.
6. Na aba **Configuração**, informe `endpoint`, `access_id`, `access_secret` e `device_id` da Tuya.
7. Inicie o App e clique em **Abrir interface web**.

## Migração da integração 0.2.6
A pasta `custom_components/tuya_ir_control` contém a integração opcional 0.3.0 sem painel lateral. Se quiser manter entidades `remote`, `button` e `climate`, substitua a pasta antiga em `/config/custom_components/tuya_ir_control` por esta e reinicie o Home Assistant.

O App funciona diretamente com a Tuya e não depende da integração para sua interface.

## Controles personalizados
Os códigos aprendidos são armazenados no volume persistente do App (`/data/custom_controls.json`). Eles não são misturados com os controles de catálogo Tuya. Ao criar um controle personalizado, escolha um controle Tuya existente como transporte para retransmitir os códigos aprendidos.

## 0.3.4
Controles personalizados são independentes dos controles de catálogo. Ao criar, escolha o tipo do equipamento; para DIY, informe também um tipo de referência. O aprendizado da primeira tecla inicia imediatamente e o controle DIY é persistido na Tuya usando a API oficial de Learning Codes.

## 0.3.6 — Catálogo x Personalizados
- **Adicionar do catálogo**: usa biblioteca Tuya; para AC usa marca + índice e comandos estruturados.
- **Personalizados**: todos os tipos, inclusive Ar-condicionado, são criados do zero e aprendidos tecla por tecla.
- O tipo escolhido no personalizado é apenas classificação/referência; não redireciona ao catálogo.
