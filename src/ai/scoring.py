import pandas as pd
import numpy as np


def compute_equity_scores(
    routes_path,
    stops_sa_path,
    sa_population_path,
    output_path
):

    print("Loading ranked route candidates...")
    routes_df = pd.read_csv(routes_path)

    print("Loading stop → Small Area mapping...")
    stops_sa_df = pd.read_csv(stops_sa_path)

    print("Loading CSO Census 2022 population data...")
    pop_df = pd.read_csv(sa_population_path)

    # -----------------------------------
    # Keep only necessary columns
    # -----------------------------------
    pop_df = pop_df[["GEOGID", "T1_1AGETT"]].copy()

    # Rename for consistency
    pop_df = pop_df.rename(columns={
        "GEOGID": "SA_ID",
        "T1_1AGETT": "population"
    })

    # Ensure string type for join
    pop_df["SA_ID"] = pop_df["SA_ID"].astype(str)

    stops_sa_df["SA_ID"] = stops_sa_df["SA_ID"].astype(str)

    # -----------------------------------
    # Merge stop → Small Area
    # -----------------------------------
    df = routes_df.merge(
        stops_sa_df[["stop_id", "SA_ID"]],
        left_on="from_stop",
        right_on="stop_id",
        how="left"
    ).drop(columns=["stop_id"])

    # -----------------------------------
    # Merge Small Area → Population
    # -----------------------------------
    df = df.merge(
        pop_df,
        on="SA_ID",
        how="left"
    )

    df["population"] = df["population"].fillna(0)

    print("Population successfully merged.")

    # -----------------------------------
    # Normalize metrics
    # -----------------------------------
    print("Normalizing metrics...")

    # Travel time normalization
    df["travel_time_norm"] = (
        df["travel_time_sec"] - df["travel_time_sec"].min()
    ) / (
        df["travel_time_sec"].max() - df["travel_time_sec"].min()
    )

    # Population normalization
    if df["population"].max() > 0:
        df["population_norm"] = (
            df["population"] - df["population"].min()
        ) / (
            df["population"].max() - df["population"].min()
        )
    else:
        df["population_norm"] = 0

    # -----------------------------------
    # Composite AI Equity Score
    # -----------------------------------
    # You can tune weights here
    w_access = 0.6
    w_population = 0.4

    df["equity_score"] = (
        w_access * df["travel_time_norm"] +
        w_population * df["population_norm"]
    )

    df = df.sort_values("equity_score", ascending=False)

    df.to_csv(output_path, index=False)

    print("\nTop 10 Equity-Prioritized Stops:")
    print(df[[
        "from_stop",
        "travel_time_sec",
        "population",
        "equity_score"
    ]].head(10))

    print("\nPhase 6 complete.")


if __name__ == "__main__":

    compute_equity_scores(
        routes_path="outputs/suggested_routes_ranked.csv",
        stops_sa_path="data/processed/Small_Area_National_Statistical_Boundaries_2022_Ungeneralised_view_-6761983190958128626.csv",
        sa_population_path="data/raw/SAPS_2022_Small_Area_UR_171024 (1).csv",
        output_path="outputs/ai_equity_ranked_routes.csv"
    )