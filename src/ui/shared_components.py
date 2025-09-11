import streamlit as st
import pandas as pd


def show_final_summary(results):
    """Show final processing summary with charts."""
    st.subheader("📊 Final Results Summary")

    # Main metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🎬 Frames Processed", results["total_frames_processed"])
    with col2:
        st.metric("👥 Total Faces", results["total_faces_detected"])
    with col3:
        st.metric("✅ Recognized", results["total_faces_recognized"])
    with col4:
        recognition_rate = 0
        if results["total_faces_detected"] > 0:
            recognition_rate = (
                results["total_faces_recognized"] / results["total_faces_detected"]
            ) * 100
        st.metric("📈 Recognition Rate", f"{recognition_rate:.1f}%")

    # Add adaptive suggestions based on recognition rate
    if results["total_faces_detected"] > 0:
        if recognition_rate < 10:
            st.warning(
                "🔍 **Low recognition rate** - Consider lowering similarity threshold to 0.2-0.3 for more matches"
            )
        elif recognition_rate < 30:
            st.info(
                "⚖️ **Moderate recognition rate** - Try lowering similarity threshold to 0.3-0.4"
            )
        elif recognition_rate > 80:
            st.success(
                "🎯 **High recognition rate** - Great! Consider slightly raising threshold for better accuracy"
            )

    # Contestant appearances
    if results["contestant_appearances"]:
        st.subheader("🏆 Contestant Appearances")

        appearances_data = []
        for name, data in results["contestant_appearances"].items():
            appearances_data.append(
                {
                    "Contestant": name,
                    "Appearances": data["total_appearances"],
                    "Avg Confidence": f"{data.get('avg_confidence', 0):.3f}",
                    "Max Confidence": f"{data.get('max_confidence', 0):.3f}",
                    "First Frame": data["first_appearance"],
                    "Last Frame": data["last_appearance"],
                }
            )

        # Sort by appearances
        appearances_data = sorted(
            appearances_data, key=lambda x: x["Appearances"], reverse=True
        )

        # Show top 10 in a nice table
        df = pd.DataFrame(appearances_data[:10])
        st.dataframe(df, use_container_width=True)

        # Create visualization
        if len(appearances_data) > 0:
            st.subheader("📊 Top Contestants Chart")
            chart_data = pd.DataFrame(
                {
                    "Contestant": [item["Contestant"] for item in appearances_data[:8]],
                    "Appearances": [
                        item["Appearances"] for item in appearances_data[:8]
                    ],
                }
            )
            st.bar_chart(chart_data.set_index("Contestant"))

        # Show statistics
        st.subheader("📈 Recognition Statistics")
        total_contestants = len(appearances_data)
        avg_appearances = sum(item["Appearances"] for item in appearances_data) / max(
            total_contestants, 1
        )

        stat_col1, stat_col2, stat_col3 = st.columns(3)
        with stat_col1:
            st.metric("🎭 Contestants Found", total_contestants)
        with stat_col2:
            st.metric("📊 Avg Appearances", f"{avg_appearances:.1f}")
        with stat_col3:
            most_appearances = max(appearances_data, key=lambda x: x["Appearances"])
            st.metric(
                "👑 Most Seen",
                f"{most_appearances['Contestant']} ({most_appearances['Appearances']})",
            )
    else:
        st.info("No contestants were recognized in this video segment.")

        # Provide helpful suggestions
        st.markdown("**💡 Suggestions to improve recognition:**")
        suggestions_col1, suggestions_col2 = st.columns(2)

        with suggestions_col1:
            st.markdown("""
            **Adjust Similarity Threshold:**
            - Current threshold might be too strict
            - Try lowering to 0.3 or 0.4
            - Lower values = more matches
            """)

        with suggestions_col2:
            st.markdown("""
            **Check Video Quality:**
            - Ensure faces are clearly visible
            - Good lighting conditions
            - Faces not too small or blurry
            """)
