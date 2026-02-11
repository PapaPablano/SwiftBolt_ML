import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
import warnings
warnings.filterwarnings('ignore')

class SuperTrendAI:
    def __init__(self, df, atr_length=10, min_mult=1, max_mult=5, step=0.5, 
                 perf_alpha=10, from_cluster='Best', max_iter=1000, max_data=10000):
        """
        SuperTrend AI with K-means Clustering
        
        Parameters:
        -----------
        df : pd.DataFrame with columns ['open', 'high', 'low', 'close']
        atr_length : int - ATR calculation period
        min_mult : float - Minimum factor for SuperTrend
        max_mult : float - Maximum factor for SuperTrend
        step : float - Step size between factors
        perf_alpha : float - Performance memory parameter
        from_cluster : str - 'Best', 'Average', or 'Worst'
        max_iter : int - Maximum K-means iterations
        max_data : int - Historical bars for calculation
        """
        self.df = df.copy()
        self.atr_length = atr_length
        self.min_mult = min_mult
        self.max_mult = max_mult
        self.step = step
        self.perf_alpha = perf_alpha
        self.from_cluster = from_cluster
        self.max_iter = max_iter
        self.max_data = max_data
        
        # Validate inputs
        if min_mult > max_mult:
            raise ValueError('Minimum factor is greater than maximum factor')
        
        # Generate factor array
        self.factors = np.arange(min_mult, max_mult + step, step)
        
    def calculate_atr(self):
        """Calculate Average True Range using EMA"""
        high = self.df['high']
        low = self.df['low']
        close = self.df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.ewm(span=self.atr_length, adjust=False).mean()
        
        return atr
    
    def calculate_supertrend(self, atr, factor):
        """Calculate SuperTrend for a given factor"""
        high = self.df['high']
        low = self.df['low']
        close = self.df['close']
        
        hl2 = (high + low) / 2
        
        # Basic bands
        upper_band = hl2 + (atr * factor)
        lower_band = hl2 - (atr * factor)
        
        # Final bands
        final_upper = pd.Series(0.0, index=self.df.index)
        final_lower = pd.Series(0.0, index=self.df.index)
        supertrend = pd.Series(0.0, index=self.df.index)
        trend = pd.Series(0, index=self.df.index)
        
        for i in range(1, len(self.df)):
            # Final upper band
            if (upper_band.iloc[i] < final_upper.iloc[i-1]) or \
               (close.iloc[i-1] > final_upper.iloc[i-1]):
                final_upper.iloc[i] = upper_band.iloc[i]
            else:
                final_upper.iloc[i] = final_upper.iloc[i-1]
            
            # Final lower band
            if (lower_band.iloc[i] > final_lower.iloc[i-1]) or \
               (close.iloc[i-1] < final_lower.iloc[i-1]):
                final_lower.iloc[i] = lower_band.iloc[i]
            else:
                final_lower.iloc[i] = final_lower.iloc[i-1]
            
            # Trend determination
            if close.iloc[i] > final_upper.iloc[i]:
                trend.iloc[i] = 1
            elif close.iloc[i] < final_lower.iloc[i]:
                trend.iloc[i] = 0
            else:
                trend.iloc[i] = trend.iloc[i-1]
            
            # SuperTrend output
            if trend.iloc[i] == 1:
                supertrend.iloc[i] = final_lower.iloc[i]
            else:
                supertrend.iloc[i] = final_upper.iloc[i]
        
        return supertrend, trend, final_upper, final_lower
    
    def calculate_performance(self, supertrend, trend):
        """Calculate performance metric for each SuperTrend"""
        close = self.df['close']
        perf = pd.Series(0.0, index=self.df.index)
        alpha = 2 / (self.perf_alpha + 1)
        
        for i in range(1, len(self.df)):
            diff = np.sign(close.iloc[i-1] - supertrend.iloc[i-1])
            price_change = close.iloc[i] - close.iloc[i-1]
            perf.iloc[i] = perf.iloc[i-1] + alpha * (price_change * diff - perf.iloc[i-1])
        
        return perf.iloc[-1]  # Return last performance value
    
    def run_kmeans_clustering(self, performances, factors):
        """Perform K-means clustering on performance data"""
        # Use recent data only
        data_limit = min(len(performances), self.max_data)
        perf_array = np.array(performances[-data_limit:]).reshape(-1, 1)
        factor_array = np.array(factors[-data_limit:])
        
        # Initialize centroids using quartiles
        q25 = np.percentile(perf_array, 25)
        q50 = np.percentile(perf_array, 50)
        q75 = np.percentile(perf_array, 75)
        
        initial_centroids = np.array([[q25], [q50], [q75]])
        
        # Perform K-means clustering
        kmeans = KMeans(n_clusters=3, init=initial_centroids, 
                       max_iter=self.max_iter, n_init=1, random_state=42)
        labels = kmeans.fit_predict(perf_array)
        
        # Group factors by cluster
        clusters = {0: [], 1: [], 2: []}
        perf_clusters = {0: [], 1: [], 2: []}
        
        for i, label in enumerate(labels):
            clusters[label].append(factor_array[i])
            perf_clusters[label].append(perf_array[i][0])
        
        # Sort clusters by average performance
        cluster_means = {k: np.mean(v) if len(v) > 0 else 0 
                        for k, v in perf_clusters.items()}
        sorted_clusters = sorted(cluster_means.items(), key=lambda x: x[1])
        
        # Map to worst, average, best
        cluster_mapping = {
            sorted_clusters[0][0]: 'Worst',
            sorted_clusters[1][0]: 'Average',
            sorted_clusters[2][0]: 'Best'
        }
        
        # Get target cluster factors
        target_label = [k for k, v in cluster_mapping.items() 
                       if v == self.from_cluster][0]
        target_factors = clusters[target_label]
        
        return np.mean(target_factors) if target_factors else self.min_mult, \
               clusters, perf_clusters, cluster_mapping
    
    def calculate(self):
        """Main calculation method"""
        atr = self.calculate_atr()
        
        # Calculate SuperTrend for all factors
        all_supertrends = []
        all_performances = []
        
        for factor in self.factors:
            st, trend, final_up, final_low = self.calculate_supertrend(atr, factor)
            perf = self.calculate_performance(st, trend)
            all_supertrends.append(st)
            all_performances.append(perf)
        
        # Perform clustering
        target_factor, clusters, perf_clusters, cluster_map = \
            self.run_kmeans_clustering(all_performances, self.factors.tolist())
        
        # Calculate final SuperTrend with target factor
        final_st, final_trend, final_upper, final_lower = \
            self.calculate_supertrend(atr, target_factor)
        
        # Calculate performance index and adaptive MA
        close = self.df['close']
        den = close.diff().abs().ewm(span=int(self.perf_alpha), adjust=False).mean()
        
        cluster_perf = np.mean([v for k, v in perf_clusters.items() 
                               if cluster_map.get(k) == self.from_cluster])
        perf_idx = max(cluster_perf, 0) / (den.iloc[-1] + 1e-10)
        
        # Normalize perf_idx to 0-1 range
        perf_idx = min(max(perf_idx, 0), 1)
        
        # Adaptive MA calculation
        perf_ama = pd.Series(final_st.iloc[0], index=self.df.index)
        for i in range(1, len(self.df)):
            perf_ama.iloc[i] = perf_ama.iloc[i-1] + \
                              perf_idx * (final_st.iloc[i] - perf_ama.iloc[i-1])
        
        # Store results
        self.df['supertrend'] = final_st
        self.df['trend'] = final_trend
        self.df['perf_ama'] = perf_ama
        self.df['target_factor'] = target_factor
        self.df['atr'] = atr  # Add ATR for risk metrics
        
        # Generate signals
        self.df['signal'] = 0
        for i in range(1, len(self.df)):
            if self.df['trend'].iloc[i-1] == 0 and self.df['trend'].iloc[i] == 1:
                self.df.loc[self.df.index[i], 'signal'] = 1  # Buy
            elif self.df['trend'].iloc[i-1] == 1 and self.df['trend'].iloc[i] == 0:
                self.df.loc[self.df.index[i], 'signal'] = -1  # Sell
        
        return self.df, {
            'target_factor': target_factor,
            'clusters': clusters,
            'perf_clusters': perf_clusters,
            'cluster_mapping': cluster_map,
            'performance_index': perf_idx
        }
