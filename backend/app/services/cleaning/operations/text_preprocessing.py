import string

import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer

from app.services.cleaning.strategy import (
    CleaningStrategyRegistry,
    OperationOutcome,
    OperationSpec,
    require_column as _require_column,
)

_NLTK_DATA_READY = False


def _ensure_nltk_data() -> None:
    """Lazily download the small NLTK corpora needed for stopwords/lemmatization/
    tokenization, once per process. Avoids requiring network access at import time."""
    global _NLTK_DATA_READY
    if _NLTK_DATA_READY:
        return
    import nltk

    for resource, package in (
        ("corpora/stopwords", "stopwords"),
        ("corpora/wordnet", "wordnet"),
        ("tokenizers/punkt_tab", "punkt_tab"),
    ):
        try:
            nltk.data.find(resource)
        except LookupError:
            nltk.download(package, quiet=True)
    _NLTK_DATA_READY = True


def _as_text_series(dataframe: pd.DataFrame, column_name: str) -> pd.Series:
    return dataframe[column_name].astype("string").fillna("")


def _count_changed(before: pd.Series, after: pd.Series) -> int:
    return int((before.astype(str) != after.astype(str)).sum())


class LowercaseStrategy:
    key = "text.lowercase"
    label = "Lowercase"
    category = "text"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_column(dataframe, spec)
        result = dataframe.copy()
        before = _as_text_series(result, column_name)
        result[column_name] = before.str.lower()
        return OperationOutcome(
            dataframe=result, affected_row_count=_count_changed(before, result[column_name]),
            affected_column_count=1, message=f"Lowercased text in '{column_name}'.",
        )


class RemovePunctuationStrategy:
    key = "text.remove_punctuation"
    label = "Remove Punctuation"
    category = "text"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_column(dataframe, spec)
        result = dataframe.copy()
        before = _as_text_series(result, column_name)
        translation = str.maketrans("", "", string.punctuation)
        result[column_name] = before.map(lambda text: text.translate(translation))
        return OperationOutcome(
            dataframe=result, affected_row_count=_count_changed(before, result[column_name]),
            affected_column_count=1, message=f"Removed punctuation in '{column_name}'.",
        )


class RemoveNumbersStrategy:
    key = "text.remove_numbers"
    label = "Remove Numbers"
    category = "text"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_column(dataframe, spec)
        result = dataframe.copy()
        before = _as_text_series(result, column_name)
        result[column_name] = before.str.replace(r"\d+", "", regex=True)
        return OperationOutcome(
            dataframe=result, affected_row_count=_count_changed(before, result[column_name]),
            affected_column_count=1, message=f"Removed digits in '{column_name}'.",
        )


class RemoveStopWordsStrategy:
    key = "text.remove_stopwords"
    label = "Remove Stop Words"
    category = "text"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        _ensure_nltk_data()
        from nltk.corpus import stopwords

        column_name = _require_column(dataframe, spec)
        stop_words = set(stopwords.words("english"))
        result = dataframe.copy()
        before = _as_text_series(result, column_name)
        result[column_name] = before.map(
            lambda text: " ".join(word for word in text.split() if word.lower() not in stop_words)
        )
        return OperationOutcome(
            dataframe=result, affected_row_count=_count_changed(before, result[column_name]),
            affected_column_count=1, message=f"Removed stop words in '{column_name}'.",
        )


class RemoveExtraSpacesStrategy:
    key = "text.remove_extra_spaces"
    label = "Remove Extra Spaces"
    category = "text"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_column(dataframe, spec)
        result = dataframe.copy()
        before = _as_text_series(result, column_name)
        result[column_name] = before.str.strip().str.replace(r"\s+", " ", regex=True)
        return OperationOutcome(
            dataframe=result, affected_row_count=_count_changed(before, result[column_name]),
            affected_column_count=1, message=f"Collapsed extra whitespace in '{column_name}'.",
        )


class TokenizeStrategy:
    key = "text.tokenize"
    label = "Tokenization"
    category = "text"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        _ensure_nltk_data()
        from nltk.tokenize import word_tokenize

        column_name = _require_column(dataframe, spec)
        result = dataframe.copy()
        before = _as_text_series(result, column_name)
        result[column_name] = before.map(word_tokenize)
        return OperationOutcome(
            dataframe=result, affected_row_count=len(result),
            affected_column_count=1, message=f"Tokenized '{column_name}' into word lists.",
        )


class LemmatizeStrategy:
    key = "text.lemmatize"
    label = "Lemmatization"
    category = "text"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        _ensure_nltk_data()
        from nltk.stem import WordNetLemmatizer

        column_name = _require_column(dataframe, spec)
        lemmatizer = WordNetLemmatizer()
        result = dataframe.copy()
        before = _as_text_series(result, column_name)
        result[column_name] = before.map(
            lambda text: " ".join(lemmatizer.lemmatize(word) for word in text.split())
        )
        return OperationOutcome(
            dataframe=result, affected_row_count=_count_changed(before, result[column_name]),
            affected_column_count=1, message=f"Lemmatized words in '{column_name}'.",
        )


class StemStrategy:
    key = "text.stem"
    label = "Stemming"
    category = "text"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        from nltk.stem import PorterStemmer

        column_name = _require_column(dataframe, spec)
        stemmer = PorterStemmer()
        result = dataframe.copy()
        before = _as_text_series(result, column_name)
        result[column_name] = before.map(
            lambda text: " ".join(stemmer.stem(word) for word in text.split())
        )
        return OperationOutcome(
            dataframe=result, affected_row_count=_count_changed(before, result[column_name]),
            affected_column_count=1, message=f"Stemmed words in '{column_name}'.",
        )


class TfidfVectorizeStrategy:
    key = "text.tfidf"
    label = "TF-IDF Vectorization"
    category = "text"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_column(dataframe, spec)
        max_features = int(spec.params.get("max_features", 50))
        vectorizer = TfidfVectorizer(max_features=max_features)
        texts = _as_text_series(dataframe, column_name)
        matrix = vectorizer.fit_transform(texts)
        feature_columns = pd.DataFrame(
            matrix.toarray(),
            columns=[f"{column_name}_tfidf_{term}" for term in vectorizer.get_feature_names_out()],
            index=dataframe.index,
        )
        result = pd.concat([dataframe.drop(columns=[column_name]), feature_columns], axis=1)
        return OperationOutcome(
            dataframe=result, affected_row_count=len(result),
            affected_column_count=len(feature_columns.columns),
            message=f"Vectorized '{column_name}' into {len(feature_columns.columns)} TF-IDF feature(s).",
        )


class BagOfWordsStrategy:
    key = "text.bow"
    label = "Bag of Words"
    category = "text"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_column(dataframe, spec)
        max_features = int(spec.params.get("max_features", 50))
        vectorizer = CountVectorizer(max_features=max_features)
        texts = _as_text_series(dataframe, column_name)
        matrix = vectorizer.fit_transform(texts)
        feature_columns = pd.DataFrame(
            matrix.toarray(),
            columns=[f"{column_name}_bow_{term}" for term in vectorizer.get_feature_names_out()],
            index=dataframe.index,
        )
        result = pd.concat([dataframe.drop(columns=[column_name]), feature_columns], axis=1)
        return OperationOutcome(
            dataframe=result, affected_row_count=len(result),
            affected_column_count=len(feature_columns.columns),
            message=f"Vectorized '{column_name}' into {len(feature_columns.columns)} bag-of-words feature(s).",
        )


def register_text_preprocessing_strategies(registry: CleaningStrategyRegistry) -> None:
    for strategy in (
        LowercaseStrategy(),
        RemovePunctuationStrategy(),
        RemoveNumbersStrategy(),
        RemoveStopWordsStrategy(),
        RemoveExtraSpacesStrategy(),
        TokenizeStrategy(),
        LemmatizeStrategy(),
        StemStrategy(),
        TfidfVectorizeStrategy(),
        BagOfWordsStrategy(),
    ):
        registry.register(strategy)
