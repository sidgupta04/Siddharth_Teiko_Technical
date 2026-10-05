"""Streamlit presentation for the completed SQLite analytics pipeline."""

from pathlib import Path

import plotly.express as px
import streamlit as st

from src.dashboard_data import filter_frequency_data, load_dashboard_data
from src.deployment import bootstrap_database, is_streamlit_cloud
from src.queries import format_bcell_average
from src.validation import POPULATIONS


def main() -> None:
    st.set_page_config(page_title="Teiko · Immune-cell analysis", page_icon="🧬", layout="wide")
    st.title("Immune-cell clinical trial analysis")
    st.caption("Loblaw Bio · Explore sample composition, response associations, and baseline subsets")
    root = Path(__file__).resolve().parent
    database = root / "clinical_trial.db"
    try:
        if not database.exists() and is_streamlit_cloud():
            bootstrap_database(database, root / "cell-count.csv")
        data = load_dashboard_data(database)
    except (FileNotFoundError, ValueError) as error:
        st.error(str(error))
        st.stop()

    overview, response, baseline = st.tabs(["Data Overview", "Response Analysis", "Baseline Subset Analysis"])
    with overview:
        st.metric("Total biological samples", f"{data['total_samples']:,}")
        st.caption("Overview controls filter this table only. Each sample has five population rows.")
        frame = data["overview"]
        controls = st.columns(4)
        search = controls[0].text_input("Sample ID contains", placeholder="sample00000")
        condition = controls[1].selectbox("Condition", [None] + sorted(frame["condition"].unique()), format_func=lambda x: "All" if x is None else x)
        treatment = controls[2].selectbox("Treatment", [None] + sorted(frame["treatment"].unique()), format_func=lambda x: "All" if x is None else x)
        timepoint = controls[3].selectbox("Time from treatment start", [None] + sorted(frame["time_from_treatment_start"].unique()), format_func=lambda x: "All" if x is None else str(x))
        filtered = filter_frequency_data(frame, search, condition, treatment, timepoint)
        st.caption(f"{filtered['sample'].nunique():,} matching samples · {len(filtered):,} population rows")
        if filtered.empty:
            st.info("No samples match these filters.")
        st.dataframe(filtered, hide_index=True, use_container_width=True,
                     column_config={"percentage": st.column_config.NumberColumn("Percentage (%)", format="%.4f")})

    with response:
        st.subheader("Responder versus non-responder composition")
        st.write("Cohort: melanoma + miraclib + PBMC + response yes/no. All timepoints are included.")
        statistics = data["statistics"]
        metrics = st.columns(2)
        metrics[0].metric("Responder samples (yes)", int(statistics.iloc[0]["responder_n"]))
        metrics[1].metric("Non-responder samples (no)", int(statistics.iloc[0]["non_responder_n"]))
        figure = px.box(
            data["responders"], x="population", y="percentage", color="response",
            category_orders={"population": list(POPULATIONS), "response": ["yes", "no"]},
            color_discrete_map={"yes": "#167D9A", "no": "#DA8053"},
            labels={"population": "Cell population", "percentage": "Relative frequency (%)", "response": "Response"},
            hover_data=["sample", "subject", "time_from_treatment_start"],
            points="outliers",
        )
        st.plotly_chart(figure, use_container_width=True)
        st.write("Two-sided Mann–Whitney U tests compare relative-frequency percentages for each population. "
                 "P-values are adjusted across all five tests using Benjamini–Hochberg FDR correction. "
                 "Significance requires adjusted_p_value < 0.05.")
        significant = statistics.loc[statistics["significant"], "population"].tolist()
        if significant:
            st.info("Populations differing between groups after correction: " + ", ".join(significant))
        else:
            st.info("No population is significant after Benjamini–Hochberg correction (adjusted p < 0.05).")
        st.dataframe(statistics, hide_index=True, use_container_width=True,
                     column_config={key: st.column_config.NumberColumn(key, format="%.6g") for key in ("p_value", "adjusted_p_value")})
        st.warning("Subjects have repeated samples at days 0, 7, and 14. This required sample-level analysis "
                   "treats observations as independent and does not account for within-subject correlation. "
                   "P-values are exploratory; these results do not establish causality or predictive performance.")

    with baseline:
        st.subheader("Baseline melanoma subset")
        st.write("Cohort: melanoma + miraclib + PBMC + time_from_treatment_start = 0.")
        st.markdown("**Qualifying baseline samples**")
        st.caption(f"{len(data['baseline_samples']):,} biological samples")
        st.dataframe(data["baseline_samples"], hide_index=True, use_container_width=True)
        columns = st.columns(3)
        for column, title, key in zip(columns, ["Samples by project", "Unique subjects by response", "Unique subjects by sex"],
                                      ["project_counts", "response_counts", "sex_counts"]):
            with column:
                st.markdown(f"**{title}**")
                st.dataframe(data[key], hide_index=True, use_container_width=True)
        st.caption("Response counts include yes/no only. Sex uses source labels M and F. Subject counts are distinct within each group.")
        st.divider()
        st.subheader("Baseline B-cell mean")
        st.write("Melanoma male responders (sex=M, response=yes, time=0), across **all sample and treatment types**.")
        st.metric("Average B-cell count", format_bcell_average(data["bcell_average"]))
        st.caption("Arithmetic mean of raw B-cell counts per qualifying sample; N/A means no matching samples.")


if __name__ == "__main__":
    main()
