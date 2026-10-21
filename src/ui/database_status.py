import streamlit as st
from pathlib import Path


def database_status_page() -> None:
    """Database status and management."""
    st.header("Database Status")

    # Get database statistics
    stats = st.session_state.db_manager.get_database_stats()

    st.subheader("ChromaDB Statistics")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Embeddings", stats["total_embeddings"])
    with col2:
        st.metric("Embedding Dimension", stats["embedding_dimension"])
    with col3:
        st.metric("Similarity Threshold", stats["similarity_threshold"])

    # Database management
    st.subheader("Database Management")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 Refresh Database"):
            with st.spinner("Refreshing database..."):
                count = st.session_state.db_manager.populate_database(
                    force_refresh=True
                )
                st.success(f"Database refreshed with {count} embeddings")
                st.rerun()

    with col2:
        if st.button("🗑️ Reset Database"):
            if st.warning("This will delete all data. Are you sure?"):
                with st.spinner("Resetting database..."):
                    st.session_state.db_manager.reset_database()
                    st.success("Database reset successfully")
                    st.rerun()

    # Show available contestants
    if stats["total_embeddings"] > 0:
        st.subheader("Available Contestants")

        # Files are named after the person; show the 編號 the database is keyed by.
        from src.database.roster import Roster

        roster = Roster.from_csv()
        contestants_dir = Path("source/photo/contestants")
        npy_files = list(contestants_dir.rglob("*_embedding.npy"))

        seen: dict[str, str] = {}
        for npy_file in npy_files:
            stem = npy_file.stem.replace("_embedding", "")
            contestant_id = roster.id_for_embedding_stem(stem)
            if contestant_id is not None:
                seen.setdefault(contestant_id, roster.label(contestant_id))

        if seen:
            labels = [seen[cid] for cid in sorted(seen, key=int)]

            # Display in columns
            num_cols = 4
            cols = st.columns(num_cols)

            for i, label in enumerate(labels):
                with cols[i % num_cols]:
                    st.text(label)
        else:
            st.warning("No contestant embedding files found")
