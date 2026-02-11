# main_production_system/dashboard/unified_dashboard.py


import sys
from pathlib import Path
import logging
from datetime import datetime

# Set up project root and dashboard paths
file_path = Path(__file__).resolve()
dashboard_dir = file_path.parent
main_prod_dir = dashboard_dir.parent
repo_root = main_prod_dir.parent
PROJECT_ROOT = repo_root
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))  # Ensure root for main_production_system
sys.path.insert(0, str(PROJECT_ROOT / 'main_production_system'))  # Fallback for dashboard subpkgs

sys.path.insert(0, str(dashboard_dir))
sys.path.insert(0, str(main_prod_dir))
sys.path.insert(0, str(repo_root))

# Configure logging before other imports
try:
    from main_production_system.dashboard.core.logging_config import setup_dashboard_logging
    setup_dashboard_logging()
    logger = logging.getLogger(__name__)
except Exception as e:
    # Fallback to basic logging if setup fails
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    logger.warning(f"Could not setup advanced logging: {e}")

# Now do imports
import streamlit as st

# ===== IMPORT PAGES =====
import importlib.util


def import_module_from_path(module_name, file_path):
    """Load a module from an absolute file path."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module



# Import pages from absolute paths (guarded)
try:
    trading_page = import_module_from_path(
        "trading_page",
        dashboard_dir / "pages" / "trading_page.py",
    )
    logger.info("✅ Trading page loaded successfully")
except Exception as e:
    logger.error(f"Failed to load trading_page: {e} - Skipping advanced trading")
    trading_page = None  # Fallback to basic page

# Temporarily disable other pages during Phase 5 integration
# try:
#     analysis_page = import_module_from_path(
#         "analysis_page",
#         dashboard_dir / "pages" / "analysis_page.py",
#     )
# except Exception as e:
#     logger.error(f"Failed to load analysis_page: {e}")
#     analysis_page = None
#
# try:
#     performance_page = import_module_from_path(
#         "performance_page",
#         dashboard_dir / "pages" / "performance_page.py",
#     )
# except Exception as e:
#     logger.error(f"Failed to load performance_page: {e}")
#     performance_page = None
#
# try:
#     monitor_page = import_module_from_path(
#         "monitor_page",
#         dashboard_dir / "pages" / "monitor_page.py",
#     )
# except Exception as e:
#     logger.error(f"Failed to load monitor_page: {e}")
#     monitor_page = None
#
# try:
#     config_page = import_module_from_path(
#         "config_page",
#         dashboard_dir / "pages" / "config_page.py",
#     )
# except Exception as e:
#     logger.error(f"Failed to load config_page: {e}")
#     config_page = None
#
# try:
#     forecast_page = import_module_from_path(
#         "forecast_page",
#         dashboard_dir / "pages" / "forecast_page.py",
#     )
# except Exception as e:
#     logger.error(f"Failed to load forecast_page: {e}")
#     forecast_page = None


# Import components
try:
    sidebar_module = import_module_from_path(
        "sidebar_controls",
        dashboard_dir / "components" / "sidebar_controls.py",
    )
    render_sidebar = sidebar_module.render_sidebar
    logger.info("✅ Sidebar controls loaded successfully")
except Exception as e:
    logger.warning(f"⚠️ Failed to load sidebar_controls: {e}")
    render_sidebar = None



# Import core modules (guarded)
try:
    from main_production_system.dashboard.core.cache_manager import (
        initialize_session_state,
        initialize_models_in_session,
    )
    from main_production_system.dashboard.core.model_manager import get_model_status
    CORE_MODULES_LOADED = True
    logger.info("✅ Core modules loaded successfully")
except ImportError as e:
    logger.warning(f"Core modules partial load: {e} - Using basics")
    CORE_MODULES_LOADED = False
    def initialize_session_state(): pass  # Dummy
    def initialize_models_in_session(): pass  # Dummy
    def get_model_status(models): return {'models_loaded': 0}


def _get_pages() -> dict:
    """Map page names to render functions (Trading only for Phase 5)."""
    pages = {}
    if trading_page and hasattr(trading_page, "render"):
        pages["📊 Trading"] = trading_page.render
    return pages


def main() -> None:
    """Run the unified dashboard application."""
    startup_time = datetime.now()
    
    try:
        st.set_page_config(
            page_title="Unified ML Trading Dashboard",
            layout="wide",
            initial_sidebar_state="expanded",
        )

        # Initialize session state and cached resources
        logger.info("[STARTUP] Initializing session state...")
        initialize_session_state()
        logger.info("[STARTUP] ✅ Session state initialized")

        # Initialize and cache models once per session
        logger.info("[STARTUP] Initializing models...")
        models = initialize_models_in_session()
        logger.info("[STARTUP] ✅ Models initialization complete")
        
        # Log model status
        if models:
            status = get_model_status(models)
            models_loaded = status.get('models_loaded', 0)
            if models_loaded == 0:
                logger.warning("[STARTUP] ⚠️ No models loaded - ML features will be unavailable")
            else:
                logger.info(f"[STARTUP] ✅ {models_loaded} model(s) loaded successfully")

        # ===== HEALTH CHECK =====
        try:
            from main_production_system.dashboard.core.healthcheck import (
                check_dashboard_health, 
                get_health_status_message,
                log_health_status
            )
            health = check_dashboard_health(models)
            log_health_status(health)
            
            # Display health status in sidebar
            st.sidebar.markdown("---")
            health_msg = get_health_status_message(health)
            if health['status'] == 'healthy':
                st.sidebar.success(health_msg)
            elif health['status'] == 'degraded':
                st.sidebar.warning(health_msg)
            else:
                st.sidebar.error(health_msg)
        except Exception as e:
            logger.warning(f"Health check failed: {e}")

        # ===== PERPLEXITY INTELLIGENCE (SIDEBAR) =====
        try:
            st.sidebar.markdown("---")
            st.sidebar.subheader("📰 Market Intelligence")
            
            # Get symbol from session state
            current_symbol = st.session_state.get('current_symbol', 'AAPL')
            
            if st.sidebar.button("Get Sentiment", use_container_width=True, help=f"Fetch Perplexity market sentiment for {current_symbol}"):
                try:
                    from main_production_system.connectors.perplexity_connector import PerplexityConnector
                    
                    with st.sidebar.spinner(f'Analyzing {current_symbol}...'):
                        connector = PerplexityConnector()
                        sentiment_data = connector.get_market_sentiment(current_symbol)
                        
                        # Store in session state
                        st.session_state['perplexity_sentiment'] = sentiment_data
                        
                        # Display metrics
                        sentiment = sentiment_data.get('sentiment', 'neutral')
                        sentiment_emoji = '🟢' if sentiment == 'positive' else '🔴' if sentiment == 'negative' else '🟡'
                        st.sidebar.metric('Sentiment', f"{sentiment_emoji} {sentiment.title()}")
                        
                        score = sentiment_data.get('sentiment_score', 0.0)
                        st.sidebar.metric('Score', f'{score:+.2f}')
                        
                        # Show brief analysis
                        analysis = sentiment_data.get('analysis', '')
                        if analysis:
                            summary = analysis[:100] + '...' if len(analysis) > 100 else analysis
                            st.sidebar.info(summary)
                        
                        st.sidebar.success('✅ Intelligence updated')
                        
                except ImportError:
                    st.sidebar.warning('⚠️ Perplexity connector not available')
                except Exception as e:
                    st.sidebar.error(f'❌ Failed to fetch sentiment: {str(e)[:50]}')
                    logger.error(f"Perplexity sidebar fetch failed: {e}")
            
            # Display cached sentiment if available
            if 'perplexity_sentiment' in st.session_state:
                cached = st.session_state['perplexity_sentiment']
                st.sidebar.caption(f"💾 Cached: {cached.get('sentiment', 'N/A')}")
                
        except Exception as e:
            logger.debug(f"Sidebar Perplexity section failed: {e}")

        # ===== NAVIGATION =====
        st.sidebar.title("🎯 Navigation")

        pages = _get_pages()
        if not pages:
            st.error("❌ No pages available. Please check logs for import errors.")
            logger.error("[STARTUP] No pages available - dashboard cannot render")
            return

        selected = st.sidebar.radio("Go to", list(pages.keys()), index=0)

        # ===== REPORT ISSUE BUTTON =====
        st.sidebar.markdown("---")
        if st.sidebar.button("📋 Report Issue", use_container_width=True, help="Open GitHub issue with context"):
            try:
                import urllib.parse
                issue_title = "Dashboard Issue Report"
                issue_body = f"""**Dashboard Issue Report**

    **Timestamp:** {datetime.now().isoformat()}
    **Page:** {selected}
    **Model Status:** {models_loaded if 'models_loaded' in locals() else 'Unknown'} model(s) loaded

    **Please describe the issue:**
    [Describe your issue here]

    **Environment:**
    - Python: {sys.version.split()[0]}
    - Streamlit: {st.__version__}

    **Logs:**
    Check `main_production_system/logs/dashboard.log` for detailed logs.
    """
                issue_url = f"https://github.com/PapaPablano/Attention-Based-Multi-Timeframe-Transformer/issues/new?title={urllib.parse.quote(issue_title)}&body={urllib.parse.quote(issue_body)}"
                st.sidebar.markdown(f"[Open GitHub Issue]({issue_url})")
            except Exception as e:
                logger.warning(f"Could not create issue link: {e}")
                st.sidebar.info("📋 Report issues by checking logs/dashboard.log")

        # ===== RENDER SELECTED PAGE =====
        if trading_page:
            try:
                pages[selected]()
            except Exception as e:
                st.error(f"❌ Error rendering page: {e}")
                logger.error(f"Page render error: {e}", exc_info=True)
        else:
            st.warning("Trading page unavailable - Check imports")

        # Log startup completion
        startup_duration = (datetime.now() - startup_time).total_seconds()
        logger.info(f"[STARTUP] ✅ Dashboard startup complete in {startup_duration:.2f} seconds")
        
    except Exception as e:
        # Centralized exception handling - log full traceback, show user-friendly message
        logger.exception("[STARTUP] ❌ Critical error during dashboard initialization")
        
        st.error("""
        ## ❌ Dashboard Failed to Start
        
        A critical error occurred during initialization. Please check the logs for details.
        
        **Common fixes:**
        - Verify all dependencies are installed: `pip install -r requirements.txt`
        - Check that model files exist in expected locations
        - Ensure Python version is 3.11+
        - Review logs/dashboard.log for detailed error information
        
        **To report this issue:**
        - Check the terminal output for the full error trace
        - Review `main_production_system/logs/dashboard.log` if available
        """)
        st.exception(e)


if __name__ == "__main__":
    main()
