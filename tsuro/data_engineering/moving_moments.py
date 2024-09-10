"""
Module for rolling window statistics.

Includes:
    - Moving Average, Moving Standard Deviation
    - Exponentially Weighted Moving Average (EWMA), Exponentially Weighted Moving Standard Deviation (EWMSD)
"""

from typing import Union

import polars as pl
from polars import LazyFrame, DataFrame

from tsuro.math import get_ewma_weights


def pl_ewma(
    df: Union[LazyFrame, DataFrame],
    ewma_cols: Union[str, list[str]],
    spans: Union[int, list[int]] = None,
    alphas: Union[float, list[float]] = None,
    partition_by: list[str] = None,
    order_by: str = None,
    min_periods: int = 1,
) -> Union[LazyFrame, DataFrame]:
    """
    Calculate exponentially weighted moving average (ewma) of column(s) via:

        y[t] = (x[t] + (1-alpha)*x[t-1] + (1-alpha)^2*x[t-2] + ... + (1-alpha)^{span-1}*x[t-span+1])/(1 + (1-alpha) + ... + (1-alpha)^{span-1})

    Use 'spans' or 'alphas' but not both. Spans default computes alphas to ensure centre of mass is at the middle index.

    Examples where both computations produce the same result:
    >>> df = ewma(df, ewma_cols = "price", spans = [3, 19])
    >>> df = ewma(df, ewma_cols = "price", alphas = [0.5, 0.1])

    Args:
        df: Polars Lazy(Data)Frame to compute ewma over.
        ewma_cols: Column(s) in Lazy(Data)Frame to compute ewma over.
        span: If provided, we use alpha = 2/(span+1). This ensures ewma centre of mass is roughly equivalent to simple moving average.
        alpha: If provided, we use this value for the decay rate alpha.
        min_periods: Minimum number of periods required to compute ewma with no nulls.
        partition_by:
        order_by:

    Returns:
        polars.LazyFrame/DataFrame
    """
    if isinstance(ewma_cols, str):
        ewma_cols = [ewma_cols]

    if isinstance(spans, int) or spans is None:
        spans = [spans]

    if isinstance(alphas, float) or alphas is None:
        alphas = [alphas]

    ewma_expressions = [
        pl.col(column)
        .ewm_mean(span=span, alpha=alpha, min_periods=min_periods)
        .over(partition_by=partition_by, order_by=order_by)
        .alias(
            f"{column}_ewma_span{span}"
            if span is not None
            else f"{column}_ewma_alpha{alpha}"
        )
        for column in ewma_cols
        for span in spans
        for alpha in alphas
    ]

    df = df.with_columns(*ewma_expressions)

    return df


def moving_average(
    df: Union[LazyFrame, DataFrame],
    moving_avg_cols: Union[str, list[str]],
    weights: Union[list[float], dict[str, list[float]]],
    partition_by: Union[str, list[str]] = None,
    order_by: str = None,
    min_periods: int = 1,
    center: bool = False,
) -> Union[LazyFrame, DataFrame]:
    """
    Calculate moving average for all specified columns with all provided weights.
    
    Parameters
    ----------
    df : LazyFrame/DataFrame
        Polars LazyFrame/DataFrame to compute moving average on.

    moving_avg_cols : str / list[str]
        Column or list of columns to compute a moving average on.

    weights : list[float] / dict[str,list[float]]
        If specified, window_size gets automatically set to len(`weights`) and weights is passed to pl.Expr.rolling_mean().
        If type(weights) == list[float], then alias suffix across all columns is set to "_ma".
        If type(weights) == dict[weight_aliases, list[float]], then all moving avg aliases will be given by f"{column}_{weight_alias}"
        Note: weights[0] corresponds to left endpoint weight preceding current row, and weights[-1] corresponds to right endpoint weight.
            If center == False, weights[-1] corresponds to weight for current row.

    partition_by : str / list[str], default = None
        Collection of columns to partition by when computing the moving average over `moving_avg_cols`.
        If None, no partition will be set.

    order_by : str, default = None
        Column to order data by when computing moving average over `moving_avg_cols`.

    center : bool, default = False
        If True, moving average window is centred on the current row.
        If False, moving average window covers len(`weights`)-1 rows preceding current row, and includes current row.

    Returns
    -------
        Polars LazyFrame/DataFrame with new moving average columns

    Examples
    --------
    >>> import polars as pl
    >>> from tsuro.data_engineering import moving_average
    >>> df = pl.DataFrame({"time": ["10:00", "10:05", "10:10"], "price": [50.50, 60.10, 55.20], "volume": [120, 300, 200]})
    >>> moving_avg_cols = ["price", "volume"]
    >>> weights = {"uniform": [1/2,1/2], "geometric": [4/7, 2/7, 1/7]}
    >>> df = moving_average(df, moving_avg_cols = moving_avg_cols, weights = weights)
    >>> print(df.columns)
    ["time", "price", "volume", "price_uniform", "price_geometric", "volume_uniform", "volume_geometric"]

    """

    if isinstance(weights, list):
        weights = {"ma": weights}

    window_sizes = [len(weight) for weight in weights.values()]

    moving_avg_expressions = [
        pl.col(column)
        .rolling_mean(
            window_size=window_size,
            weights=weight,
            center=center,
            min_periods=min_periods,
        )
        .over(partition_by=partition_by, order_by=order_by)
        .alias(f"{column}_{weight_alias}")
        for column in moving_avg_cols
        for weight_alias, weight, window_size in zip(
            weights.keys(), weights.values(), window_sizes
        )
    ]

    df = df.with_columns(*moving_avg_expressions)

    return df


def ewma(
    df: Union[LazyFrame, DataFrame],
    ewma_cols: Union[str, list[str]],
    spans: Union[int, list[int]],
    alphas: Union[float, list[float]] = None,
    partition_by: list[str] = None,
    order_by: str = None,
    min_periods: int = 1,
) -> Union[LazyFrame, DataFrame]:
    """
    Calculate exponentially weighted moving average (ewma) of column(s) via:

        y[t] = (x[t] + (1-alpha)*x[t-1] + (1-alpha)^2*x[t-2] + ... + (1-alpha)^{span-1}*x[t-span+1])/(1 + (1-alpha) + ... + (1-alpha)^{span-1})

    Parameters
    ----------
        df : Polars LazyFrame/DataFrame
            Dataframe to compute ewma over.

        ewma_cols : str / list[str]
            Column(s) in dataframe to compute exponentially weighted moving average over.

        spans : int / list[int]
            Required argument. If alphas = None, we set alpha = 2/(span+1). This ensures ewma centre of mass is roughly equivalent to simple moving average.

        alphas: float / list[float], default = None
            Optional. If provided, we use this value for the decay rate alpha.

        partition_by : str / list[str], default = None
            Collection of columns to partition by when computing the ewma over `ewma_cols`.
            If None, no partition will be set.

        order_by : str, default = None
            Column to order data by when computing ewma over `ewma_cols`.

        min_periods: int, default = 1
            Minimum number of periods required to compute ewma with no nulls.

    Returns
    -------
        Polars LazyFrame/DataFrame with new ewma columns
    """

    if isinstance(ewma_cols, str):
        ewma_cols = [ewma_cols]

    if isinstance(spans, int):
        spans = [spans]

    if isinstance(alphas, float) or alphas is None:
        alphas = [alphas]

    weights = {
        (
            f"ewma_span{span}" if alpha is None else f"ewma_span{span}_alpha{alpha}"
        ): get_ewma_weights(span=span, alpha=alpha)
        for span in spans
        for alpha in alphas
    }

    return moving_average(
        df=df,
        moving_avg_cols=ewma_cols,
        weights=weights,
        partition_by=partition_by,
        order_by=order_by,
        min_periods=min_periods,
    )
