import anthropic

client = anthropic.Anthropic(api_key="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")

models = client.models.list()
for model in models:
    print(model.id)
