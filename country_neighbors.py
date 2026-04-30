import json

from config import Config

with open(Config.COUNTRY_NEIGHBORS_PATH, "r", encoding="utf-8") as f:
    COUNTRY_NEIGHBORS = json.load(f)


# Ближайшие соседи
def first_neighbors(country):
    return set(COUNTRY_NEIGHBORS.get(country, []))


# Соседи через одну страну
def second_neighbors(country):
    first = first_neighbors(country)
    second = set()
    for neighbor in first:
        second.update(COUNTRY_NEIGHBORS.get(neighbor, []))
    second.discard(country)
    return second - first


MAX_SCORE_PER_ROUND = 1000


# Очки за ответ
def calculate_score(correct, selected):
    if not selected:
        return 0, "no_answer"
    if selected == correct:
        return 1000, "exact"
    if selected in first_neighbors(correct):
        return 700, "neighbor_1"
    if selected in second_neighbors(correct):
        return 400, "neighbor_2"
    return 0, "wrong"
