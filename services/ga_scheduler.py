import time
import random
import itertools

from services.schedule_metrics import analyse_schedule


def fitness_function(
        order: list[int],
        tiles,
        telescope,
        deadlines,
        merits,
        start_position
) -> float:
    """
    Score a tile permutation by its expected Figure of Merit.

    Delegates the timeline, step-CDF, and FoM computation to
    :func:`services.schedule_metrics.analyse_schedule`, so the GA fitness
    path and the UI / reporting path share one implementation of the
    scoring model.

    ``deadlines`` may include a trailing ``+inf`` sentinel (matching the
    ``deadlines_full`` convention used throughout the GA and UI). The
    sentinel is stripped before delegating, since ``analyse_schedule``
    takes only the finite deadlines and re-appends ``+inf`` internally.
    """
    ordered_tiles = [tiles[i] for i in order]
    deadlines_finite = [d for d in deadlines if d != float("inf")]
    metric = analyse_schedule(
        ordered_tiles,
        telescope,
        start_position,
        deadlines_finite,
        merits=merits,
    )
    return float(metric.fom)

def run_ga(
        tiles,
        telescope,
        deadlines,
        merits,
        start_position,
        n_generations=100,
        pop_size=50,
        time_points=None,
        progress_callback=None,
        max_opt_seconds: float | None = None,
        planned_opt_seconds: float | None = None,
) -> tuple[list[int], list[dict]]:
    """
    Run a Genetic Algorithm (GA) that optimizes schedule order (permutation) for FoM.

    :param max_opt_seconds: optional hard wall-clock for GA runtime.
           planned_opt_seconds:
                If provided, evaluate all candidates using deadlines shifted by this fixed planning budget
                If None, shift by current elapsed time
    """

    if tiles is None:
        return [], []

    if deadlines is None or merits is None:
        raise ValueError("No deadlines or merits")

    # Build initial population
    n = len(tiles)
    if n <= 1:
        return list(range(n)), []

    # One individual = current order
    current_order = list(range(n))

    # Start population with the current order
    population = [current_order]

    # Rest = random permutations
    # We want pop_size individuals total, we already have 1 (current_order),
    # So we need pop_size - 1 more.
    for _ in range(pop_size - 1):
        ind = list(range(n))

        # Shuffle inds in place
        random.shuffle(ind)

        # Adds a new ordering to the population
        population.append(ind)

    time_points_sorted = sorted(time_points) if time_points else []
    next_cut_idx = 0

    start_wall = time.monotonic()

    def evaluate_population(
        pop: list[list[int]],
        elapsed_s: float,
    ) -> list[float]:
        """Evaluate population fitness.

        If planned_opt_seconds is set, GA optimises for the remaining search window after that planned budget.
        Otherwise, use elapsed wall-clock time.
        """
        effective_elapsed = (
            float(planned_opt_seconds)
            if planned_opt_seconds is not None
            else float(elapsed_s)
        )
        effective_deadlines = shift_deadlines(deadlines, effective_elapsed)
        return [
            fitness_function(ind, tiles, telescope, effective_deadlines, merits, start_position)
            for ind in pop
        ]

    elapsed = time.monotonic() - start_wall
    fitness_values = evaluate_population(population, elapsed)

    history: list[dict] = []

    # GA generations
    for gen_idx in range(n_generations):
        elapsed = time.monotonic() - start_wall

        # Stop criterion, explicit optimisation-time budget
        # This decouples logging cut points from actual stopping
        if max_opt_seconds is not None and elapsed >= float(max_opt_seconds):
            break

        current_best_idx = max(range(len(population)), key=lambda i: fitness_values[i])
        current_best_fitness = float(fitness_values[current_best_idx])
        if progress_callback is not None:
            progress_callback(
                {
                    "generation": gen_idx + 1,
                    "elapsed_s": elapsed,
                    "best_fom": current_best_fitness,
                }
            )

        # Record snapshots for any time cutoffs reached so far
        if time_points_sorted:
            current_best_individual = population[current_best_idx][:]
            while next_cut_idx < len(time_points_sorted) and elapsed >= time_points_sorted[next_cut_idx]:
                t_cut = float(time_points_sorted[next_cut_idx])
                fom_at_cut = fitness_function(
                    order=current_best_individual,
                    tiles=tiles,
                    telescope=telescope,
                    deadlines=shift_deadlines(deadlines, t_cut),
                    merits=merits,
                    start_position=start_position,
                )
                history.append(
                    {
                        "t_opt": t_cut,
                        "order": current_best_individual[:],
                        "FoM": fom_at_cut,
                    }
                )
                next_cut_idx += 1

        # Elitism and reproduction
        num_elites = 1
        tournament_size = 3
        mutation_rate = 0.1

        # 1) Get elites
        n_pop = len(population)
        elite_indices = sorted(range(n_pop), key=lambda i: fitness_values[i], reverse=True)[:num_elites]
        elites = [population[i] for i in elite_indices]

        # 2) Build offspring
        offspring = []
        while len(offspring) < n_pop - num_elites:
            parent_a, parent_b = tournament_select(population, fitness_values, tournament_size)
            child = order_crossover(parent_a, parent_b)
            child = swap_mutation(child, mutation_rate)
            offspring.append(child)

        # 3) New population = elites + offspring
        new_population = elites + offspring

        population = new_population

        # 4) Re-evaluate fitness for the new population
        elapsed = time.monotonic() - start_wall
        fitness_values = evaluate_population(population, elapsed)

    # Final best order from the last evaluated population
    if not population:
        return [], history

    best_idx = max(range(len(population)), key=lambda i: fitness_values[i])
    best_individual = population[best_idx][:]

    if time_points_sorted and next_cut_idx < len(time_points_sorted):
        current_best_individual = best_individual[:]
        for idx in range(next_cut_idx, len(time_points_sorted)):
            t_cut = float(time_points_sorted[idx])
            fom_at_cut = fitness_function(
                order=current_best_individual,
                tiles=tiles,
                telescope=telescope,
                deadlines=shift_deadlines(deadlines, t_cut),
                merits=merits,
                start_position=start_position,
            )
            history.append(
                {
                    "t_opt": t_cut,
                    "order": current_best_individual[:],
                    "FoM": fom_at_cut,
                }
            )

    return best_individual, history

def tournament_select(
        population: list[list[int]],
        fitness_values: list[float],
        tournament_size: int = 3
) -> tuple[list[int], list[int]]:
    """Select two parents via tournament selection.
        Each parent is the best among tournament_size random individuals.
        Parents can be the same individual."""

    n_pop = len(population)

    # Parent A: run tournament
    indices_a = random.choices(range(n_pop), k=tournament_size)
    winner_idx_a = max(indices_a, key=lambda i: fitness_values[i])
    parent_a = population[winner_idx_a]

    # Parent A: run another tournament
    indices_b = random.choices(range(n_pop), k=tournament_size)
    winner_idx_b = max(indices_b, key=lambda i: fitness_values[i])
    parent_b = population[winner_idx_b]

    return parent_a, parent_b

def order_crossover(parent_a: list[int], parent_b: list[int]) -> list[int]:
    """
    Order Crossover (OX): copy a segment from parent_a into the child;
    fill the rest with remaining values in the order they appear in parent_b.
    """
    n = len(parent_a)
    if n <= 1:
        return list(parent_a)

    i = random.randint(0, n - 2)
    j = random.randint(i + 1, n)

    child: list[int | None] = [None] * n
    for pos in range(i, j):
        child[pos] = parent_a[pos]

    in_segment = set(parent_a[i:j])
    remaining = [x for x in parent_b if x not in in_segment]

    idx = 0
    for pos in range(n):
        if child[pos] is None:
            child[pos] = remaining[idx]
            idx += 1

    return [x for x in child if x is not None]

def swap_mutation(
        individual: list[int],
        mutation_rate: float=0.1
) -> list[int]:
    if len(individual) < 2:
        return list(individual)

    if random.random() < mutation_rate:
        # Create a copy to avoid in-place modification if necessary
        mutation_ind = individual.copy()

        # Pick 2 unique indices
        idx1, idx2 = random.sample(range(len(individual)), 2)

        # Swap the values
        mutation_ind[idx1], mutation_ind[idx2] = mutation_ind[idx2], mutation_ind[idx1]

        return mutation_ind

    return individual

def shift_deadlines(deadlines, t_opt: float):
    """Shift finite deadlines left by t_opt to account for GA runtime.

    D_i^(effective) = max(D_i - t_opt, 0)
    D_z = +inf stays +inf.

    Returns a list same length as deadlines."""

    shifted = []
    for d in deadlines:
        if isinstance(d, float) and (d == float("inf") or d == float("-inf")):
            shifted.append(d)
        else:
            # finite deadline
            shifted.append(max(float(d) - t_opt, 0.0))

    return shifted

def brute_force_best_order(
        tiles,
        telescope,
        deadlines,
        merits,
        start_position,
        t_opt: float | None = None,
):
    """Compute the true optimal permutation by enumerating all orders.

    Intended only for small n (factorial growth).
    If `t_opt` is provided, evaluates using effective deadlines shifted by t_opt.

    Returns:
        (best_order_indices, best_fom)
    """

    n = len(tiles)
    best_order = None
    best_fom = float("-inf")

    effective_deadlines = deadlines if t_opt is None else shift_deadlines(deadlines, float(t_opt))

    for perm in itertools.permutations(range(n)):
        fom = fitness_function(
            order=list(perm),
            tiles=tiles,
            telescope=telescope,
            deadlines=effective_deadlines,
            merits=merits,
            start_position=start_position
        )
        if fom > best_fom:
            best_fom = fom
            best_order = list(perm)

    return best_order, best_fom


