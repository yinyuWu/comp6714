import os
import sys
import string
import json
import nltk
from nltk.stem import WordNetLemmatizer, PorterStemmer
from nltk import word_tokenize, pos_tag

class Index():
    def __init__(self):
        self.wnl = WordNetLemmatizer()
        self.stemmer = PorterStemmer()
        self.sentence_end_list = ['.', '!', '?']
        self.punctuation_list = list(string.punctuation)
        self.token_dividers_list = set(self.punctuation_list) - set(self.sentence_end_list)
        self.token_dividers_list = list(self.token_dividers_list)
        self.inverted_index = {}

    def printIndex(self, number_documents, number_tokens, number_terms):
        print("Total number of documents: " + str(number_documents))
        print("Total number of tokens: " + str(number_tokens))
        print("Total number of terms: " + str(number_terms))

    # get all docs
    def create_index(self, document_folder, index_folder):
        doc_list = os.listdir(document_folder)
        doc_list = [int(doc) for doc in doc_list]
        doc_list.sort()
        # print(doc_list)
        number_documents = len(doc_list)
        number_tokens = 0
        for doc_id in doc_list:
            # read document
            position = 0
            file_name = os.path.join(document_folder, str(doc_id))
            doc = open(file_name, 'r')
            doc_content = doc.read()
            tokens = word_tokenize(doc_content)
            
            # tokens in document
            for token, tag in pos_tag(tokens):
                # skip punctuation
                if (len(token) == 1 and (not token.isalpha()) and (token not in self.sentence_end_list)):
                    continue
                # ignore 's after noun
                if (tag == 'POS'):
                    continue
                # divide word by punctuation
                start = 0
                token_list = []
                for i in range(len(token)):
                    if (token[i] in self.token_dividers_list):
                        if (i > start):
                            token_list.append(token[start : i])
                        start = i + 1
                token_list.append(token[start:])
                # preprocess
                for token_item in token_list:
                    # ignore numeric tokens
                    if (token_item.replace('.', '', 1).isdigit()):
                        continue
                    # end of sentence
                    if (token_item in self.sentence_end_list):
                        token_item = '&'
                    # ignore full stops for abbreviations
                    if (len(token_item) > 1 and '.' in token_item):
                        token_item = token_item.replace('.', '')
                    # lemmatize token
                    token_item = self.wnl.lemmatize(token_item)
                    # stem token
                    token_item = self.stemmer.stem(token_item)
                    # case folding
                    token_item = token_item.lower()
                    
                    # add token to index
                    if token_item in self.inverted_index:
                        postings = self.inverted_index[token_item]
                        if doc_id in postings:
                            postings[doc_id].append(position)
                        else:
                            postings[doc_id] = [position]
                    else:
                        self.inverted_index[token_item] = {doc_id: [position]}
                    # count token
                    if (token_item != '&'):
                        number_tokens += 1
                        position += 1
            doc.close()
        # create folder if not exist
        if (not os.path.exists(index_folder)):
            os.makedirs(index_folder)
        # write to file
        index_file_name = os.path.join(index_folder, 'index.json')
        index_file = open(index_file_name, 'w')
        json.dump(self.inverted_index, index_file)

        # print info of index
        number_terms = len(self.inverted_index)
        if ('.' in self.inverted_index):
            number_terms -= 1
        if ('!' in self.inverted_index):
            number_terms -= 1
        if ('?' in self.inverted_index):
            number_terms -= 1
        self.printIndex(number_documents, number_tokens, number_terms)


if __name__ == "__main__":
    nltk.download('wordnet', quiet=True)
    nltk.download('punkt', quiet=True)
    document_folder = sys.argv[1]
    indexes_folder = sys.argv[2]
    index_builder = Index()
    index_builder.create_index(document_folder, indexes_folder)