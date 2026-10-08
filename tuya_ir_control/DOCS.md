# Tuya IR Control 0.4.0

App com interface Ingress, controles de catálogo e personalizados e publicação automática pelo MQTT Discovery. Não depende de integração customizada.

## Atualizar a instalação existente

1. Faça backup. Substitua o código da pasta atual do App pelo conteúdo de `tuya_ir_control/`, mantendo o slug e a instalação existentes.
2. Recarregue a loja, use Atualizar/Reconstruir e reinicie **somente o App**. Não desinstale e não apague `/data`: os controles e códigos aprendidos continuam em custom_controls.json.
3. Deixe `mqtt_enabled: true` e `mqtt_host` vazio se o MQTT for um serviço do Supervisor. O App obtém host, porta e credenciais automaticamente.
4. Confirme que a integração MQTT padrão do HA está configurada, com Discovery habilitado. Os dispositivos aparecem em Configurações → Dispositivos e serviços → MQTT.

Se o broker for externo ou a detecção automática falhar, preencha mqtt_host, mqtt_port, mqtt_username, mqtt_password e mqtt_tls nas opções. Use somente endereço/IP em mqtt_host. O padrão é porta 1883; certificados TLS precisam ser confiáveis e corresponder ao host. O prefixo Discovery padrão homeassistant é usado.

Instalação local: pasta `/addons/tuya_ir_control`. Em repositório GitHub, atualize a mesma pasta usada pelo Supervisor. O ZIP não publica automaticamente no repositório nem modifica sua instalação.

## Ar-condicionado

Os controles AC estruturados, de catálogo ou personalizados com biblioteca Tuya, agora têm:

- No App: campo de temperatura, botões **− / +** e Enviar temperatura.
- No HA: entidade **climate**, com temperatura desejada, modos, ventilação e ligar/desligar.
- Botões MQTT **Aumentar temperatura** e **Diminuir temperatura**, para usar também em dashboards/automações.

O ajuste é de **16 a 30 °C, em passos de 1 °C**, conforme o conjunto padrão IR Tuya. Temperaturas fracionadas ou fora da faixa são recusadas antes do envio. Ao atingir um limite, o comando de incremento/decremento é recusado sem transmitir um sinal repetido.

No App, −/+ ajustam a temperatura escolhida no campo e enviam esse valor. Os botões MQTT −/+ usam a última temperatura desejada salva pelo App. A referência inicial é 24 °C, indicada como inicial; não é uma medição nem prova da configuração física do aparelho. Alterar a temperatura não envia um comando adicional de ligar.

Modos: frio, quente, automático, ventilação e seco; velocidades: automática, baixa, média e alta. A biblioteca selecionada e o equipamento podem não suportar todos esses modos/velocidades. Escolher um modo no HA envia o modo e depois Power ON; Off envia Power OFF. Esses controles realmente emitem IR quando acionados pelo usuário.

A transmissão IR não confirma o estado físico do equipamento. As entidades mostram a seleção inicial ou o último comando aceito pela Tuya, com atributo `estado_estimado: true` e horário do último comando. Não publicamos temperatura ambiente medida. Usar o controle físico ou outro aplicativo pode deixar essa estimativa desatualizada.

## Teclas e controles aprendidos

Cada tecla de catálogo e cada tecla aprendida é publicada como uma entidade **button**, agrupada no dispositivo correspondente. As teclas personalizadas AC existentes continuam disponíveis como botões, além do climate e −/+; os códigos aprendidos não são enviados no Discovery nem nos tópicos de comando.

Um controle marcado como ar-condicionado mas criado somente com sinais IR brutos continua tendo botões para os sinais gravados. Não é possível gerar todas as temperaturas a partir de um único sinal aprendido. Para temperatura arbitrária e climate, use um controle AC com biblioteca/índice Tuya, como no assistente de ar-condicionado. Não convertemos nem descartamos automaticamente seus códigos aprendidos.

Controles de catálogo usados como transporte de um controle personalizado não são duplicados no MQTT. Controles personalizados independentes mantêm seus IDs e não são unidos só por terem a mesma categoria.

## Sincronização do cadastro e funcionamento MQTT

Cadastros locais são revistos a cada 5 segundos; catálogo/teclas Tuya são consultados a cada 60 segundos e ao abrir/atualizar o painel. Renomear preserva IDs; excluir controles/teclas remove o Discovery correspondente após uma consulta completa. Falhas e respostas incompatíveis não são tratadas como lista vazia, nem apagam as entidades já conhecidas.

O App guarda os tópicos publicados em `/data/mqtt_registry.json` para limpar entidades removidas mesmo após reinício. Guarde esse arquivo nos backups com custom_controls.json e ac_state.json. Não mude o Device ID para outro hub supondo que seja o mesmo conjunto de controles: os identificadores incluem o hub.

Discovery e estados são retidos. Ao receber o nascimento do HA em homeassistant/status ou reconectar ao broker, o App republica a configuração e os estados. O Last Will e o desligamento normal informam offline. Controles cujo catálogo não pôde ser carregado na inicialização ficam indisponíveis até serem reconhecidos; configurações antigas são preservadas até confirmação.

Comandos são QoS 0, não retidos e não têm nova tentativa automática. Mensagens retidas recebidas após inscrição/reconexão são ignoradas. Inicializar o App, descobrir entidades ou republicar estados **não envia comandos IR**. Somente acionar uma entidade ou botão do painel transmite um comando. Mensagens inválidas ou para teclas removidas são recusadas.

Se a Tuya rejeitar um envio, a estimativa não é alterada para simular sucesso. Erros MQTT aparecem nos logs sem expor credenciais. O resultado do comando também é publicado de forma transitória em `tuya_ir/HUB_HASH/command_result`. O painel mostra a conexão MQTT no topo.

## Migração da integração antiga

Este pacote não inclui custom_components. Depois de confirmar as entidades MQTT e ajustar as referências de dashboards/automações, desative/remova a antiga integração Tuya IR Control pela interface do HA. Não remova a integração MQTT padrão, que recebe os controles do App.

Os IDs das novas entidades pertencem à integração MQTT e podem diferir dos antigos; confira os IDs exibidos no seu HA. Não é necessário reiniciar o HA para o Discovery funcionar quando a integração MQTT já está carregada.

## Validação

21 testes Python, testes funcionais do frontend em Node e verificações de sintaxe passaram. Cobrem comandos AC, limites, persistência, incrementos concorrentes, traduções de modo/ventilação, falso sucesso, teclas aprendidas/catálogo, IDs, remoções, falha cloud, mensagens retidas, integração HTTP e detecção automática do Supervisor.

Um teste usa aiomqtt 2.5.1 real com um servidor de protocolo MQTT em localhost. Todos os envios Tuya foram simulados. Não houve acesso à sua Tuya/HA/MQTT ou transmissão física. A construção Docker e a aparência/cadastro efetivo no seu HA ainda precisam ser validados na instalação real.

Referências oficiais: https://www.home-assistant.io/integrations/climate.mqtt/ ; https://www.home-assistant.io/integrations/button.mqtt/ ; https://developer.tuya.com/en/docs/cloud/infrared-air-conditioner-apis?id=Kb3oe9ehg02fn
