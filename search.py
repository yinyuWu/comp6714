import os
import sys
import re
import json
from nltk.stem import WordNetLemmatizer, PorterStemmer

# load index
index_folder = sys.argv[1]
index_file_name = os.path.join(index_folder, "index.json")
index_file = open(index_file_name)
index_dict = json.load(index_file)

wnl = WordNetLemmatizer()
stemmer = PorterStemmer()

########## Helper Functions ##########
def add_or(curr, next):
    if (curr == '(' or next == ')'):
        return False
    if (is_operator(curr) or is_operator(next)):
        return False
    return True

def is_operator(token):
    if (token == '&' or token == '+s' or token == '/s' or token == '|'):
        return True
    elif ((token[0] == '+' or token[0] == '/') and
            re.match(r'^(\d+)$', token[1:])):
        return True
    else:
        return False

def cmp_operator(left, right):
    order = {}
    order['('] = -1
    order[')'] = -1
    order['&'] = 0
    order['/s'] = 1
    order['+s'] = 2
    order['/n'] = 3
    order['+n'] = 4
    order['|'] = 5

    if ((left[0] == '+' or left[0] == '/') and
            re.match(r'^(\d+)$', left[1:])):
        left = left[0] + 'n'
    if ((right[0] == '+' or right[0] == '/') and
            re.match(r'^(\d+)$', right[1:])):
        right = right[0] + 'n'
    return order[left] > order[right]

def sentence_pos(end_list, token_pos):
    start = 0
    end = end_list[-1]
    for i in range(len(end_list) - 1):
        if (token_pos >= end_list[i]
            and token_pos < end_list[i+1]):
            start = end_list[i]
            end = end_list[i+1]
            break
    return start, end
    
def process_query(query):
    # ignore '\n', split query by space
    query = query.replace('\n', '')
    query = query.replace('(', '( ')
    query = query.replace(')', ' )')
    query_list = query.split(" ")

    phrase_start = -1
    query_tokens = []
    # extract phrases from query
    for i in range(len(query_list)):
        if (query_list[i][0] == '\"' and query_list[i][-1] != '\"'):
            phrase_start = i
        elif (query_list[i][-1] == '\"' and query_list[i][0] != '\"'):
            query_tokens.append(' '.join(query_list[phrase_start:i+1]))
            phrase_start = -1
        else:
            if (phrase_start == -1):
                query_tokens.append(query_list[i])
    # add | as OR connector
    token_index = 0
    while (token_index < len(query_tokens) - 1):
        if (add_or(query_tokens[token_index], query_tokens[token_index + 1])):
            query_tokens.insert(token_index + 1, '|')
            token_index += 2
        else:
            token_index += 1

    # re-write chaining mixed connectors
    # token_index = 0
    # while (token_index < len(query_tokens)):
    #     token = query_tokens[token_index]
    #     if (is_operator(token) and token != '|' and token != '&'):
    #         query_tokens, start, end = rewrite_query(query_tokens, token_index)
    #         token_index = end + 1
    #     else:
    #         token_index += 1

    # order of query
    # infix to postfix
    op_stack = []
    ordered_query = []

    for query_token in query_tokens:
        if (query_token == '('):
            op_stack.append(query_token)
        elif (query_token == ')'):
            while (len(op_stack) > 0 and op_stack[-1] != '('):
                ordered_query.append(op_stack.pop())
            if (len(op_stack) > 0 and op_stack[-1] == '('):
                op_stack.pop()
        elif (is_operator(query_token)):
            while (len(op_stack) > 0 and
                    cmp_operator(op_stack[-1], query_token)):
                ordered_query.append(op_stack.pop())
            op_stack.append(query_token)
        else:
            ordered_query.append(query_token)
    while (len(op_stack) > 0):
        ordered_query.append(op_stack.pop())
    return ordered_query


########## Postings of token ##########
def token_postings(token):
    if (len(token) > 1 and '.' in token):
        token = token.replace('.', '')
    token = wnl.lemmatize(token)
    token = stemmer.stem(token)
    token = token.lower()
    if (not token in index_dict):
        return {}
    else:
        return index_dict[token]

def phrase_postings(phrase):
    phrase = phrase.replace('\"', "")
    phrase_list = phrase.split(" ")
    result = token_postings(phrase_list[0])
    prev = result
    for i in range(len(phrase_list) - 1):
        curr = token_postings(phrase_list[i+1])
        posting = ordered_numeric_operation('+1', prev, curr)
        result = and_operation(result, posting)
        prev = curr
    return result

def get_postings(token):
    if (token[0] != "\""):
        return token_postings(token)
    else:
        return phrase_postings(token)


########## Operations Functions ##########
def or_operation(left, right):
    result = {}
    left_docs = list(left.keys())
    left_docs = [int(doc) for doc in left_docs]
    right_docs = list(right.keys())
    right_docs = [int(doc) for doc in right_docs]
    left_index = 0
    right_index = 0
    # merge two dictionary
    while (left_index < len(left_docs) and (right_index < len(right_docs))):
        left_docID = left_docs[left_index]
        right_docID = right_docs[right_index]
        if (left_docID < right_docID):
            result[str(left_docID)] = left[str(left_docID)]
            left_index += 1
        elif (left_docID > right_docID):
            result[str(right_docID)] = right[str(right_docID)]
            right_index += 1
        else:
            result[str(left_docID)] = sorted(set(left[str(left_docID)] + right[str(right_docID)]))
            left_index += 1
            right_index += 1
    # append rest to result
    while (left_index < len(left_docs)):
        left_docID = left_docs[left_index]
        result[str(left_docID)] = left[str(left_docID)]
        left_index += 1
    while (right_index < len(right_docs)):
        right_docID = right_docs[right_index]
        result[str(right_docID)] = right[str(right_docID)]
        right_index += 1
    return result

def and_operation(left, right):
    result = {}
    left_docs = list(left.keys())
    left_docs = [int(doc) for doc in left_docs]
    right_docs = list(right.keys())
    right_docs = [int(doc) for doc in right_docs]
    left_index = 0
    right_index = 0
    while (left_index < len(left_docs) and (right_index < len(right_docs))):
        left_docID = left_docs[left_index]
        right_docID = right_docs[right_index]
        if (left_docID == right_docID):
            result[str(left_docID)] = sorted(set(left[str(left_docID)] + right[str(right_docID)]))
            left_index += 1
            right_index += 1
        else:
            if (left_docs[left_index] < right_docs[right_index]):
                left_index += 1
            else:
                right_index += 1
    return result

def numeric_operation(operation, left, right):
    result = {}
    n_terms = int(operation[1:])
    left_docs = list(left.keys())
    left_docs = [int(doc) for doc in left_docs]
    right_docs = list(right.keys())
    right_docs = [int(doc) for doc in right_docs]
    left_index = 0
    right_index = 0
    while (left_index < len(left_docs) and (right_index < len(right_docs))):
        if (left_docs[left_index] == right_docs[right_index]):
            docID = left_docs[left_index]
            pp1 = left[str(docID)]
            pp2 = right[str(docID)]
            for pp1_pos in pp1:
                for pp2_pos in pp2:
                    if (abs(pp1_pos - pp2_pos) <= n_terms):
                        if (docID in result):
                            result[str(docID)].append(pp1_pos)
                            result[str(docID)].append(pp2_pos)
                        else:
                            result[str(docID)] = [pp1_pos, pp2_pos]
                    elif (pp2_pos - pp1_pos > n_terms):
                        break
            if (docID in result):
                result[str(docID)] = sorted(set(result[str(docID)]))
            left_index += 1
            right_index += 1
        else:
            if (left_docs[left_index] < right_docs[right_index]):
                left_index += 1
            else:
                right_index += 1
    return result

def ordered_numeric_operation(operation, left, right):
    result = {}
    n_terms = int(operation[1:])
    left_docs = list(left.keys())
    left_docs = [int(doc) for doc in left_docs]
    right_docs = list(right.keys())
    right_docs = [int(doc) for doc in right_docs]
    left_index = 0
    right_index = 0
    while (left_index < len(left_docs) and (right_index < len(right_docs))):
        if (left_docs[left_index] == right_docs[right_index]):
            docID = left_docs[left_index]
            pp1 = left[str(docID)]
            pp2 = right[str(docID)]
            for pp1_pos in pp1:
                for pp2_pos in pp2:
                    if (pp2_pos > pp1_pos and pp2_pos - pp1_pos <= n_terms):
                        if (docID in result):
                            result[str(docID)].append(pp1_pos)
                            result[str(docID)].append(pp2_pos)
                        else:
                            result[str(docID)] = [pp1_pos, pp2_pos]
                    elif (pp2_pos - pp1_pos > n_terms):
                        break
            if (docID in result):
                result[str(docID)] = sorted(set(result[str(docID)]))
            left_index += 1
            right_index += 1
        else:
            if (left_docs[left_index] < right_docs[right_index]):
                left_index += 1
            else:
                right_index += 1
    return result

def sentence_operation(left, right):
    result = {}
    left_docs = list(left.keys())
    left_docs = [int(doc) for doc in left_docs]
    right_docs = list(right.keys())
    right_docs = [int(doc) for doc in right_docs]
    left_index = 0
    right_index = 0
    while (left_index < len(left_docs) and (right_index < len(right_docs))):
        if (left_docs[left_index] == right_docs[right_index]):
            docID = left_docs[left_index]
            end_list = index_dict["&"]
            end_list = end_list[str(docID)]
            pp1 = left[str(docID)]
            pp2 = right[str(docID)]
            for pp1_pos in pp1:
                # start/end of sentence
                start, end = sentence_pos(end_list, pp1_pos)
                # find pp2 in the same sentence
                for pp2_pos in pp2:
                    if (pp2_pos >= start and pp2_pos < end):
                        if (docID in result):
                            result[str(docID)].append(pp1_pos)
                            result[str(docID)].append(pp2_pos)
                        else:
                            result[str(docID)] = [pp1_pos, pp2_pos]
                    elif (pp2_pos > end):
                        break
            if (docID in result):
                result[str(docID)] = sorted(set(str(result[docID])))
            left_index += 1
            right_index += 1
        else:
            if (left_docs[left_index] < right_docs[right_index]):
                left_index += 1
            else:
                right_index += 1
    return result

def ordered_sentence_operation(left, right):
    result = {}
    left_docs = list(left.keys())
    left_docs = [int(doc) for doc in left_docs]
    right_docs = list(right.keys())
    right_docs = [int(doc) for doc in right_docs]
    left_index = 0
    right_index = 0
    while (left_index < len(left_docs) and (right_index < len(right_docs))):
        if (left_docs[left_index] == right_docs[right_index]):
            docID = left_docs[left_index]
            end_list = index_dict["&"]
            end_list = end_list[str(docID)]
            pp1 = left[str(docID)]
            pp2 = right[str(docID)]
            for pp1_pos in pp1:
                # start/end of sentence
                start, end = sentence_pos(end_list, pp1_pos)
                # find pp2 in the same sentence
                for pp2_pos in pp2:
                    if (pp2_pos > start and pp2_pos < end and pp1_pos < pp2_pos):
                        if (docID in result):
                            result[str(docID)].append(pp1_pos)
                            result[str(docID)].append(pp2_pos)
                        else:
                            result[str(docID)] = [pp1_pos, pp2_pos]
                    elif (pp2_pos > end):
                        break
            if (docID in result):
                result[str(docID)] = sorted(set(result[str(docID)]))
            left_index += 1
            right_index += 1
        else:
            if (left_docs[left_index] < right_docs[right_index]):
                left_index += 1
            else:
                right_index += 1
    return result

def query_operation(operation, left, right):
    if (operation == '|'):
        return or_operation(left, right)
    elif (operation[0] == '+' and re.match(r'^(\d+)$', operation[1:])):
        return ordered_numeric_operation(operation, left, right)
    elif (operation[0] == '/' and re.match(r'^(\d+)$', operation[1:])):
        return numeric_operation(operation, left, right)
    elif (operation == '/s'):
        return sentence_operation(left, right)
    elif (operation == '+s'):
        return ordered_sentence_operation(left, right)
    elif (operation == '&'):
        return and_operation(left, right)


def search(query):
    query_list = process_query(query)
    postings_list = []
    # print(query_list)
    while (len(query_list) > 0):
        query_token = query_list.pop(0)
        if (not is_operator(query_token)):
            postings = get_postings(query_token)
        else:
            right = postings_list.pop()
            left = postings_list.pop()
            postings = query_operation(query_token, left, right)
        # print(postings)
        postings_list.append(postings)
    result = list(postings_list[-1].keys())
    result = [int(doc) for doc in result]
    result.sort()
    for docID in result:
        print(docID)


while (True):
    query = sys.stdin.readline()
    if (query):
        search(query)
    else:
        sys.exit(0)
