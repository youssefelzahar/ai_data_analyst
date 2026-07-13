from app.services.cleaning.operations.duplicates import register_duplicate_strategies
from app.services.cleaning.operations.encoding import register_encoding_strategies
from app.services.cleaning.operations.missing_values import register_missing_value_strategies
from app.services.cleaning.operations.outliers import register_outlier_strategies
from app.services.cleaning.operations.scaling import register_scaling_strategies
from app.services.cleaning.operations.skew_transform import register_skew_transform_strategies
from app.services.cleaning.operations.text_preprocessing import register_text_preprocessing_strategies
from app.services.cleaning.operations.type_conversion import register_type_conversion_strategies
from app.services.cleaning.strategy import CleaningStrategyRegistry


def build_default_registry() -> CleaningStrategyRegistry:
    """Assembles the registry of every built-in cleaning strategy.

    Adding a new technique means writing one strategy class and one more
    `registry.register(...)` call in its operations module — nothing here
    or in the pipeline executor needs to change.
    """
    registry = CleaningStrategyRegistry()
    register_missing_value_strategies(registry)
    register_duplicate_strategies(registry)
    register_type_conversion_strategies(registry)
    register_outlier_strategies(registry)
    register_encoding_strategies(registry)
    register_scaling_strategies(registry)
    register_skew_transform_strategies(registry)
    register_text_preprocessing_strategies(registry)
    return registry
