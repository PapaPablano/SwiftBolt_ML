"""
Cache performance monitoring dashboard.

Author: Cursor Agent
Created: 2025-01-27
"""

import streamlit as st
from main_production_system.dashboard.core.redis_cache_manager import _cache_manager


def render_cache_monitoring_tab():
    """Render cache statistics and controls."""
    st.header("💾 Cache Performance Monitoring")

    stats = _cache_manager.get_stats()

    if stats.get('status') == 'redis_unavailable':
        st.warning("⚠️ Redis unavailable - using Streamlit fallback cache")
        st.info(
            "To enable Redis caching for multi-user scalability:\n"
            "1. Install Redis: `brew install redis` (macOS) or `apt-get install redis-server` (Linux)\n"
            "2. Start Redis: `redis-server`\n"
            "3. Set environment variables:\n"
            "   - REDIS_HOST=localhost\n"
            "   - REDIS_PORT=6379"
        )
        return

    if stats.get('status') == 'redis_active':
        st.success("✅ Redis cache active")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Keys", stats.get('total_keys', 0))

        with col2:
            st.metric("Namespace Keys", stats.get('namespace_keys', 0))

        with col3:
            hit_rate = stats.get('hit_rate', 0)
            st.metric("Cache Hit Rate", f"{hit_rate:.1%}")

        with col4:
            st.metric("Memory Used", stats.get('used_memory_human', 'N/A'))

        st.markdown("---")

        # Detailed statistics
        st.subheader("📊 Detailed Statistics")

        col1, col2 = st.columns(2)

        with col1:
            st.metric("Cache Hits", stats.get('hits', 0))
            st.metric("Cache Misses", stats.get('misses', 0))

        with col2:
            total_requests = stats.get('hits', 0) + stats.get('misses', 0)
            if total_requests > 0:
                hit_pct = (stats.get('hits', 0) / total_requests) * 100
                miss_pct = (stats.get('misses', 0) / total_requests) * 100
                st.metric("Hit Percentage", f"{hit_pct:.1f}%")
                st.metric("Miss Percentage", f"{miss_pct:.1f}%")
            else:
                st.metric("Hit Percentage", "N/A")
                st.metric("Miss Percentage", "N/A")

        st.markdown("---")

        # Cache management
        st.subheader("🔧 Cache Management")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("🗑️ Clear Cache", type="primary"):
                deleted = _cache_manager.clear_namespace()
                st.success(f"Cleared {deleted} keys from cache")
                st.rerun()

        with col2:
            st.info(f"Cache namespace: `{_cache_manager.namespace}`")

        # Performance insights
        st.markdown("---")
        st.subheader("💡 Performance Insights")

        hit_rate = stats.get('hit_rate', 0)
        if hit_rate >= 0.85:
            st.success(
                f"Excellent cache performance! Hit rate of {hit_rate:.1%} indicates efficient caching. "
                "Most requests are served from cache, reducing API costs and improving response times."
            )
        elif hit_rate >= 0.60:
            st.info(
                f"Good cache performance. Hit rate of {hit_rate:.1%} is above average. "
                "Consider adjusting TTL values if you notice stale data."
            )
        elif hit_rate >= 0.40:
            st.warning(
                f"Moderate cache performance. Hit rate of {hit_rate:.1%} suggests many cache misses. "
                "This could indicate frequent data updates or short TTL values."
            )
        else:
            st.error(
                f"Low cache performance. Hit rate of {hit_rate:.1%} indicates most requests bypass the cache. "
                "Review TTL settings and cache key generation to improve efficiency."
            )

    elif stats.get('status') == 'error':
        st.error(f"❌ Error getting cache statistics: {stats.get('message', 'Unknown error')}")


if __name__ == "__main__":
    st.set_page_config(page_title="Cache Monitoring", layout="wide")
    render_cache_monitoring_tab()

