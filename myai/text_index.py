"""Small deterministic BM25 baseline for offline retrieval and intent routing.

No search labels, prices or stock are embedded into generated customer answers.
"""
from collections import Counter, defaultdict
import math
import re
from .retrieval import normalize


def text_terms(text):
    return re.findall(r'[a-z0-9]+', normalize(text))


class BM25Index:
    def __init__(self, documents):
        self.postings = defaultdict(dict)
        self.lengths = {}
        for doc_id, content in documents:
            if doc_id in self.lengths:
                raise ValueError('Duplicate document id: '+str(doc_id))
            frequencies = Counter(text_terms(content))
            self.lengths[doc_id] = sum(frequencies.values())
            for term, frequency in frequencies.items():
                self.postings[term][doc_id] = frequency
        self.count = len(self.lengths)
        self.average_length = sum(self.lengths.values())/max(self.count, 1) or 1

    def search(self, query, limit=10):
        scores = defaultdict(float)
        for term in set(text_terms(query)):
            matches = self.postings.get(term, {})
            idf = math.log(1+(self.count-len(matches)+.5)/(len(matches)+.5))
            for doc_id, frequency in matches.items():
                normalization = 1.2*(1-.75+.75*self.lengths[doc_id]/self.average_length)
                scores[doc_id] += idf*frequency*2.2/(frequency+normalization)
        return sorted(scores.items(), key=lambda item:(-item[1],str(item[0])))[:limit]
