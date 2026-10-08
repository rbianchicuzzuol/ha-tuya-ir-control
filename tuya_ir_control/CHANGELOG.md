# 0.4.0

- MQTT Discovery com detecção automática do serviço MQTT do Supervisor e conexão manual opcional.
- Climate para AC estruturado de catálogo/personalizado: temperatura, modo, ventilação e power.
- Botões aumentar/diminuir temperatura em 1 °C no MQTT e campo com −/+ no painel, substituindo presets fixos de catálogo.
- Entidades button para teclas de catálogo e sinais personalizados, sem expor os códigos IR no MQTT.
- Estado estimado persistente, compartilhado por UI/MQTT, alterado somente após envio aceito pela Tuya.
- Validação de temperatura 16–30, comandos não retidos/QoS 0 e recusa de ações retidas ao reconectar.
- Discovery/estado retidos, republicação no nascimento/reconexão, Last Will e disponibilidade por controle.
- IDs estáveis e limpeza de Discovery após exclusão confirmada; preserva entidades em falha de catálogo/teclas.
- Remove a necessidade de integração customizada; mantém configurações e códigos existentes do App.
- Gravação JSON atômica e persistência dos IDs legados na inicialização, sem sobrescrever arquivo inválido.

## 0.3.6
- Restaura Remover nos controles de catálogo.
- AC personalizado passa a usar biblioteca AC estruturada e permite montar teclas personalizadas sem aprendizado bruto.
- DIY e demais personalizados mantêm aprendizado IR bruto.
- Controles AC vinculados a personalizados não aparecem duplicados em Configurados.

# Changelog

## 0.3.5
- Corrige Personalizados > Ar-condicionado: agora cria um controle DIY independente e inicia aprendizado IR tecla a tecla.
- O catálogo de ar-condicionado é acessado somente por "Adicionar do catálogo".
- `category_id` passa a ser apenas metadado de classificação em controles personalizados; nunca é usado para substituir/deduplicar controles.
- Migração defensiva preserva todos os controles personalizados existentes e garante UUID local único.
- Mantém múltiplos ACs simultâneos, cada um identificado pelo próprio `remote_id`/UUID.

## 0.3.4
- Catálogo AC usa category_id 5 como referência primária.
