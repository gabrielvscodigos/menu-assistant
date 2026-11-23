"""Tests for grounded answering, with a fake LLM and a fake embedder."""

from collections.abc import Sequence

import pytest
from chromadb.api.models.Collection import Collection

from menu_assistant.ingest.indexer import index_menu
from menu_assistant.llm import ChatMessage
from menu_assistant.models import Allergen, Course, DietaryFlag, Dish, Menu
from menu_assistant.rag.answer import (
    NO_MATCH_TEXTS,
    SAFETY_NOTICES,
    AnswerService,
    enforce_list_citations,
    verify_citations,
)
from menu_assistant.rag.language import Language
from menu_assistant.rag.prompt import SYSTEM_PROMPT, build_user_message, format_dish
from menu_assistant.rag.restrictions import Restrictions
from menu_assistant.retrieval.embeddings import Embedder
from menu_assistant.retrieval.search import MenuRetriever, RetrievedDish


class FakeLLM:
    """Returns a scripted reply and records every prompt it receives."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[tuple[str, list[ChatMessage]]] = []

    def generate(self, system: str, messages: Sequence[ChatMessage]) -> str:
        self.calls.append((system, list(messages)))
        return self.reply

    def check(self) -> None:
        pass

    @property
    def last_prompt(self) -> str:
        return self.calls[-1][1][-1].content


@pytest.fixture
def retriever(sample_menu: Menu, collection: Collection, fake_embedder: Embedder) -> MenuRetriever:
    index_menu(sample_menu, collection, fake_embedder)
    return MenuRetriever(collection, fake_embedder)


def service(retriever: MenuRetriever, llm: FakeLLM, k: int = 25) -> AnswerService:
    return AnswerService(retriever, llm, k=k)


# --- verify_citations ----------------------------------------------------------


@pytest.fixture
def dishes(sample_menu: Menu) -> list[Dish]:
    return [d for d in sample_menu.dishes if d.id in {"edamame", "pork-gyoza"}]


def test_verify_citations_keeps_retrieved_ids_in_order(dishes: list[Dish]) -> None:
    text = "Try Edamame [edamame] or Gyoza [pork-gyoza]. Edamame [edamame] again."

    cleaned, cited = verify_citations(text, dishes)

    assert cleaned == text
    assert cited == ["edamame", "pork-gyoza"]


def test_verify_citations_strips_ids_that_were_not_retrieved(dishes: list[Dish]) -> None:
    cleaned, cited = verify_citations("Try Lasagna [lasagna] or Edamame [edamame].", dishes)

    assert cleaned == "Try Lasagna or Edamame [edamame]."
    assert cited == ["edamame"]


def test_verify_citations_rewrites_dish_names_to_ids(dishes: list[Dish]) -> None:
    cleaned, cited = verify_citations("1. [Salted Edamame] is light.", dishes)

    assert cleaned == "1. [edamame] is light."
    assert cited == ["edamame"]


def test_verify_citations_leaves_other_bracketed_text_alone(dishes: list[Dish]) -> None:
    text = "Ask for sauce [on the side] with Edamame [edamame]."

    assert verify_citations(text, dishes) == (text, ["edamame"])


# --- prompt --------------------------------------------------------------------


def test_prompt_contains_dish_facts_restrictions_and_question(sample_menu: Menu) -> None:
    dish = next(d for d in sample_menu.dishes if d.id == "dan-dan-noodles")
    restrictions = Restrictions(exclude_allergens=frozenset({Allergen.MILK}))

    message = build_user_message(
        "spicy please?", [RetrievedDish(dish=dish, similarity=0.9, score=0.9)], restrictions
    )

    assert format_dish(dish) in message
    assert "Allergens: gluten, mustard, peanuts, sesame, soy" in message
    assert "HARD RESTRICTIONS ALREADY APPLIED: excludes milk" in message
    assert message.endswith("GUEST QUESTION: spicy please?")


def test_disliked_ingredients_reach_retrieval_and_prompt(retriever: MenuRetriever) -> None:
    llm = FakeLLM("Try Edamame [edamame].")

    answer = service(retriever, llm).answer("sem cebola nem alho, o que você sugere?")

    assert answer.restrictions.exclude_ingredients == {"onion", "garlic"}
    assert "chana-masala" not in {item.dish.id for item in answer.retrieved}
    assert "HARD RESTRICTIONS ALREADY APPLIED: without garlic, onion" in llm.last_prompt
    assert answer.notice == SAFETY_NOTICES[Language.PT]


# --- AnswerService -------------------------------------------------------------


def test_answer_uses_system_prompt_and_reports_citations(retriever: MenuRetriever) -> None:
    llm = FakeLLM("You'll love Dan Dan Noodles [dan-dan-noodles]!")

    answer = service(retriever, llm).answer("spicy noodles")

    system, messages = llm.calls[0]
    assert system == SYSTEM_PROMPT
    assert [m.role for m in messages] == ["user"]
    assert answer.cited_dish_ids == ["dan-dan-noodles"]
    assert [item.dish.id for item in answer.cited_dishes] == ["dan-dan-noodles"]
    assert answer.notice is None


def test_detected_allergy_filters_dishes_before_the_llm_sees_them(
    retriever: MenuRetriever,
) -> None:
    llm = FakeLLM("Try the Dan Dan Noodles [dan-dan-noodles].")

    answer = service(retriever, llm).answer("I'm allergic to peanuts, any noodles?")

    assert answer.restrictions.exclude_allergens == {Allergen.PEANUTS}
    assert "[dan-dan-noodles]" not in llm.last_prompt
    assert all(Allergen.PEANUTS not in item.dish.allergens for item in answer.retrieved)
    # The LLM ignored the rules and cited a filtered-out dish: the citation is removed.
    assert answer.cited_dish_ids == []
    assert "[dan-dan-noodles]" not in answer.text
    assert answer.notice == SAFETY_NOTICES[Language.EN]


def test_explicit_and_detected_restrictions_are_combined(retriever: MenuRetriever) -> None:
    llm = FakeLLM("ok")
    explicit = Restrictions(exclude_allergens=frozenset({Allergen.SOY}))

    answer = service(retriever, llm).answer("anything vegan?", explicit)

    assert answer.restrictions == Restrictions(
        exclude_allergens=frozenset({Allergen.SOY}), require_flags=frozenset({DietaryFlag.VEGAN})
    )
    # Vegan dishes without soy on the sample menu.
    assert {item.dish.id for item in answer.retrieved} == {
        "chana-masala",
        "falafel-plate",
        "mango-sticky-rice",
    }


def test_no_matching_dish_answers_without_calling_the_llm(retriever: MenuRetriever) -> None:
    llm = FakeLLM("should not be used")
    explicit = Restrictions(
        exclude_allergens=frozenset({Allergen.SESAME}), require_flags=frozenset({DietaryFlag.HALAL})
    )

    answer = service(retriever, llm).answer("vegan halal food", explicit)

    assert llm.calls == []
    assert answer.text == NO_MATCH_TEXTS[Language.EN]
    assert answer.retrieved == []
    assert answer.notice == SAFETY_NOTICES[Language.EN]


def test_question_about_allergens_gets_notice_even_without_restrictions(
    retriever: MenuRetriever,
) -> None:
    answer = service(retriever, FakeLLM("It lists peanuts.")).answer("does the ramen have peanuts?")

    assert not answer.restrictions
    assert answer.notice == SAFETY_NOTICES[Language.EN]


def test_notice_follows_the_question_language(retriever: MenuRetriever) -> None:
    answer = service(retriever, FakeLLM("Sugiro o Elote [elote].")).answer(
        "Tenho alergia a amendoim, o que você sugere?"
    )

    assert answer.language == Language.PT
    assert answer.notice == SAFETY_NOTICES[Language.PT]


def test_no_match_text_follows_the_question_language(retriever: MenuRetriever) -> None:
    explicit = Restrictions(
        exclude_allergens=frozenset({Allergen.SESAME}), require_flags=frozenset({DietaryFlag.HALAL})
    )

    answer = service(retriever, FakeLLM("unused")).answer("quiero algo vegano y halal", explicit)

    assert answer.language == Language.ES
    assert answer.text == NO_MATCH_TEXTS[Language.ES]
    assert answer.notice == SAFETY_NOTICES[Language.ES]


def test_every_language_has_every_fixed_text() -> None:
    assert set(SAFETY_NOTICES) == set(NO_MATCH_TEXTS) == set(Language)


# --- course --------------------------------------------------------------------


def test_prompt_states_the_requested_course(sample_menu: Menu) -> None:
    dish = next(d for d in sample_menu.dishes if d.id == "tiramisu")
    retrieved = [RetrievedDish(dish=dish, similarity=0.9, score=0.9)]

    message = build_user_message("a dessert?", retrieved, Restrictions(), Course.DESSERT)

    assert "COURSE REQUESTED: dessert" in message
    assert "COURSE REQUESTED" not in build_user_message("a dessert?", retrieved, Restrictions())


def test_detected_course_limits_dishes_to_that_course(retriever: MenuRetriever) -> None:
    answer = service(retriever, FakeLLM("ok")).answer("a vegan dessert, please")

    assert answer.course == Course.DESSERT
    assert [item.dish.id for item in answer.retrieved] == ["mango-sticky-rice"]


def test_explicit_course_overrides_the_detected_one(retriever: MenuRetriever) -> None:
    answer = service(retriever, FakeLLM("ok")).answer("a dessert", course=Course.STARTER)

    assert answer.course == Course.STARTER
    assert answer.retrieved
    assert all(item.dish.course == Course.STARTER for item in answer.retrieved)


def test_course_alone_does_not_trigger_the_safety_notice(retriever: MenuRetriever) -> None:
    answer = service(retriever, FakeLLM("ok")).answer("what desserts do you have?")

    assert answer.course == Course.DESSERT
    assert answer.notice is None


# --- list citations ------------------------------------------------------------


@pytest.fixture
def desserts(sample_menu: Menu) -> list[Dish]:
    return [d for d in sample_menu.dishes if d.id in {"mango-sticky-rice", "tiramisu"}]


def test_list_items_citing_retrieved_dishes_are_kept(desserts: list[Dish]) -> None:
    text = "Options:\n1. Mango Sticky Rice [mango-sticky-rice] - vegan.\n2. [tiramisu] - creamy."

    assert enforce_list_citations(text, desserts) == (text, [])


def test_list_item_naming_a_retrieved_dish_gets_its_citation(desserts: list[Dish]) -> None:
    text = "- **Mango Sticky Rice** - sweet and vegan."

    cleaned, removed = enforce_list_citations(text, desserts)

    assert cleaned == "- **Mango Sticky Rice** [mango-sticky-rice] - sweet and vegan."
    assert removed == []


def test_invented_list_items_are_removed_and_the_list_renumbered(desserts: list[Dish]) -> None:
    text = (
        "I recommend:\n\n"
        "1. Mango Sticky Rice [mango-sticky-rice] - classic.\n"
        "2. Coconut Ice Cream - refreshing.\n"
        "3. Tiramisu [tiramisu] - creamy.\n"
        "4) Fresh Fruit Salad - light.\n"
        "  - an indented detail stays\n\n"
        "Enjoy!"
    )

    cleaned, removed = enforce_list_citations(text, desserts)

    assert cleaned == (
        "I recommend:\n\n"
        "1. Mango Sticky Rice [mango-sticky-rice] - classic.\n"
        "2. Tiramisu [tiramisu] - creamy.\n"
        "  - an indented detail stays\n\n"
        "Enjoy!"
    )
    assert removed == ["2. Coconut Ice Cream - refreshing.", "4) Fresh Fruit Salad - light."]


def test_answer_drops_invented_dishes_and_records_them(retriever: MenuRetriever) -> None:
    llm = FakeLLM("1. Mango Sticky Rice - vegan.\n2. Coconut Ice Cream - also vegan.")

    answer = service(retriever, llm).answer("a vegan dessert?")

    assert answer.text == "1. Mango Sticky Rice [mango-sticky-rice] - vegan."
    assert answer.cited_dish_ids == ["mango-sticky-rice"]
    assert answer.removed_items == ["2. Coconut Ice Cream - also vegan."]


# --- follow-up questions -------------------------------------------------------


def test_follow_up_keeps_restrictions_from_earlier_questions(retriever: MenuRetriever) -> None:
    history = [
        ChatMessage(role="user", content="I'm allergic to peanuts, any spicy noodles?"),
        ChatMessage(role="assistant", content="Try the Spicy Miso Ramen [spicy-miso-ramen]."),
    ]

    answer = service(retriever, FakeLLM("Try Edamame [edamame].")).answer(
        "and a starter?", history=history
    )

    assert answer.restrictions.exclude_allergens == {Allergen.PEANUTS}
    assert all(Allergen.PEANUTS not in item.dish.allergens for item in answer.retrieved)
    assert answer.notice == SAFETY_NOTICES[Language.EN]


def test_follow_up_sends_earlier_turns_before_the_menu_message(retriever: MenuRetriever) -> None:
    history = [
        ChatMessage(role="user", content="something spicy"),
        ChatMessage(role="assistant", content="Try the Elote [elote]."),
    ]
    llm = FakeLLM("Try Edamame [edamame].")

    service(retriever, llm).answer("anything lighter?", history=history)

    messages = llm.calls[-1][1]
    assert messages[:2] == history
    assert messages[2].role == "user"
    assert messages[2].content.endswith("GUEST QUESTION: anything lighter?")


def test_short_follow_up_answers_in_the_conversation_language(retriever: MenuRetriever) -> None:
    history = [
        ChatMessage(role="user", content="Tenho alergia a amendoim, tem algo apimentado?"),
        ChatMessage(role="assistant", content="Sugiro o Elote [elote]."),
    ]

    answer = service(retriever, FakeLLM("Sugiro o Edamame [edamame].")).answer(
        "tacos?", history=history
    )

    assert answer.language == Language.PT
    assert answer.notice == SAFETY_NOTICES[Language.PT]


def test_course_is_not_carried_over_from_earlier_questions(retriever: MenuRetriever) -> None:
    history = [
        ChatMessage(role="user", content="a vegan dessert?"),
        ChatMessage(role="assistant", content="Try the Mango Sticky Rice [mango-sticky-rice]."),
    ]

    answer = service(retriever, FakeLLM("Try Edamame [edamame].")).answer(
        "and something salty?", history=history
    )

    assert answer.course is None
    assert answer.restrictions.require_flags == {DietaryFlag.VEGAN}
