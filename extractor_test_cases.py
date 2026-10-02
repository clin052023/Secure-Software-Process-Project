''' 
Courtney Lin, Nicholas Marden
Task 1 - Extractor
'''

# ---------------------------------- #
#     File for Testing Extractor     #
# ---------------------------------- #

from extractor import document_reader, gemma_3_1b, output_txt_collector
from prompt_constructors import zero_shot, few_shot, chain_of_thought

# change path on your own device
doc = document_reader("/Users/courtneylin/Documents/VSC projects and classwork/comp5700/docker-cis-v0.pdf")

#zeroshot = zero_shot(doc[:1000])
#print(zeroshot)
#fewshot = few_shot(doc[:1000])
#print(fewshot)
chainofthought = chain_of_thought(doc[:1000])
print(chainofthought)