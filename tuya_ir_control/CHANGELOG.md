# Changelog

## 0.3.5
- Corrige Personalizados > Ar-condicionado: agora cria um controle DIY independente e inicia aprendizado IR tecla a tecla.
- O catálogo de ar-condicionado é acessado somente por "Adicionar do catálogo".
- `category_id` passa a ser apenas metadado de classificação em controles personalizados; nunca é usado para substituir/deduplicar controles.
- Migração defensiva preserva todos os controles personalizados existentes e garante UUID local único.
- Mantém múltiplos ACs simultâneos, cada um identificado pelo próprio `remote_id`/UUID.

## 0.3.4
- Catálogo AC usa category_id 5 como referência primária.
