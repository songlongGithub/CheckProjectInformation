"""Deterministic stdlib equivalent of fuzzywuzzy+Levenshtein's used scorers."""
import re


def ratio(a, b):
    if a == b:
        return 100
    if not a or not b:
        return 0
    # Levenshtein ratio uses normalized indel similarity, equivalent to LCS.
    if len(a) < len(b):
        a, b = b, a
    previous = [0] * (len(b) + 1)
    for ca in a:
        current = [0]
        for j, cb in enumerate(b, 1):
            current.append(previous[j-1] + 1 if ca == cb else max(previous[j], current[-1]))
        previous = current
    return int(round(200 * previous[-1] / (len(a) + len(b))))


def full_process(text, force_ascii=False):
    if force_ascii:
        text = ''.join(c for c in text if not 128 <= ord(c) < 256)
    return re.sub(r'(?ui)\W', ' ', text).lower().strip()


def token_sort_ratio(a, b):
    return ratio(' '.join(sorted(full_process(a, True).split())),
                 ' '.join(sorted(full_process(b, True).split())))


class fuzz:
    ratio = staticmethod(ratio)
    token_sort_ratio = staticmethod(token_sort_ratio)


class process:
    @staticmethod
    def extractOne(query, choices, scorer):
        query = full_process(query)
        results = [(c, scorer(query, full_process(c))) for c in choices]
        return max(results, key=lambda x: x[1]) if results else None
