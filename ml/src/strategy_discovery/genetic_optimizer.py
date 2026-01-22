"""Genetic algorithm for automated strategy discovery."""

import logging
from dataclasses import dataclass
from typing import Callable, List
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class OptimizationConfig:
    """GA configuration."""
    population_size: int = 50
    generations: int = 100
    mutation_rate: float = 0.1
    crossover_rate: float = 0.7
    elite_size: int = 5


class GeneticOptimizer:
    """Genetic algorithm for strategy optimization."""
    
    def __init__(self, config: OptimizationConfig):
        self.config = config
        self.population: List = []
        self.best_individual = None
        self.best_fitness = -np.inf
        logger.info(f"GeneticOptimizer initialized: pop={config.population_size}, gen={config.generations}")
    
    def optimize(self, fitness_func: Callable, gene_bounds: List[tuple]) -> tuple:
        """Run genetic algorithm.
        
        Args:
            fitness_func: Function(individual) -> fitness_score
            gene_bounds: List of (min, max) for each gene
        
        Returns:
            (best_individual, best_fitness)
        """
        n_genes = len(gene_bounds)
        
        # Initialize population
        self.population = [
            np.array([np.random.uniform(bounds[0], bounds[1]) for bounds in gene_bounds])
            for _ in range(self.config.population_size)
        ]
        
        # Evolution
        for generation in range(self.config.generations):
            # Evaluate fitness
            fitness_scores = [fitness_func(ind) for ind in self.population]
            
            # Track best
            max_idx = np.argmax(fitness_scores)
            if fitness_scores[max_idx] > self.best_fitness:
                self.best_fitness = fitness_scores[max_idx]
                self.best_individual = self.population[max_idx].copy()
            
            # Selection, crossover, mutation
            self.population = self._evolve_population(fitness_scores, gene_bounds)
            
            if (generation + 1) % 10 == 0:
                logger.info(f"Gen {generation+1}/{self.config.generations}: Best fitness={self.best_fitness:.4f}")
        
        return self.best_individual, self.best_fitness
    
    def _evolve_population(self, fitness_scores, gene_bounds):
        """Create next generation."""
        # Elite preservation
        elite_indices = np.argsort(fitness_scores)[-self.config.elite_size:]
        new_pop = [self.population[i].copy() for i in elite_indices]
        
        # Create offspring
        while len(new_pop) < self.config.population_size:
            # Tournament selection
            parent1 = self._tournament_select(fitness_scores)
            parent2 = self._tournament_select(fitness_scores)
            
            # Crossover
            if np.random.rand() < self.config.crossover_rate:
                child = self._crossover(parent1, parent2)
            else:
                child = parent1.copy()
            
            # Mutation
            if np.random.rand() < self.config.mutation_rate:
                child = self._mutate(child, gene_bounds)
            
            new_pop.append(child)
        
        return new_pop[:self.config.population_size]
    
    def _tournament_select(self, fitness_scores, tournament_size=3):
        """Tournament selection."""
        indices = np.random.choice(len(self.population), tournament_size, replace=False)
        tournament_fitness = [fitness_scores[i] for i in indices]
        winner_idx = indices[np.argmax(tournament_fitness)]
        return self.population[winner_idx].copy()
    
    def _crossover(self, parent1, parent2):
        """Single-point crossover."""
        point = np.random.randint(1, len(parent1))
        child = np.concatenate([parent1[:point], parent2[point:]])
        return child
    
    def _mutate(self, individual, gene_bounds):
        """Gaussian mutation."""
        gene_idx = np.random.randint(len(individual))
        individual[gene_idx] += np.random.randn() * 0.1 * (gene_bounds[gene_idx][1] - gene_bounds[gene_idx][0])
        individual[gene_idx] = np.clip(individual[gene_idx], gene_bounds[gene_idx][0], gene_bounds[gene_idx][1])
        return individual


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=" * 70)
    print("Genetic Optimizer - Self Test")
    print("=" * 70)
    
    # Test function: maximize x^2 + y^2 in range [-10, 10]
    def fitness(individual):
        return -(individual[0]**2 + individual[1]**2)  # Negative because we minimize distance from 0
    
    config = OptimizationConfig(population_size=20, generations=50)
    optimizer = GeneticOptimizer(config)
    
    best, fitness_val = optimizer.optimize(fitness, [(-10, 10), (-10, 10)])
    print(f"\nBest solution: {best}")
    print(f"Fitness: {fitness_val:.4f}")
    print("\n✅ Genetic optimizer test complete!")
