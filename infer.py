import csv

import torch
from transformers import (
    GPT2LMHeadModel,
    GPT2TokenizerFast,
)

tokenizer = GPT2TokenizerFast.from_pretrained('models/test')
model = GPT2LMHeadModel.from_pretrained('models/test')

with open('data/orig/input/dev.tsv', 'r', encoding='utf8') as f:
    reader = csv.reader(f, delimiter='\t')
    next(reader)
    for row in reader:
        input = tokenizer.encode(row[0] + ' === ', return_tensors='pt')
        model_output = model.generate(
            input,
            do_sample=True,
            max_length=128,
            top_k=42,
            top_n=0.69,
            temperature=1.2,
            num_return_sequences=1,
            early_stopping=True,
        )
        for out in model_output:
            print(tokenizer.decode(out))

        model_output = model.generate(
            input,
            max_length=128,
            num_beams=10,
            no_repeat_ngram_size=3,
            num_return_sequences=1,
            early_stopping=True
        )
        for out in model_output:
            print(tokenizer.decode(out))
        break
