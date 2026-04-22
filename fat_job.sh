#!/bin/bash
#SBATCH --job-name=fat_job
#SBATCH --time=12:00:00
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=24
#SBATCH --partition=ecsstudents_l4
#SBATCH --mem=16G
#SBATCH --output=logs/fatw-%j.out
#SBATCH --error=logs/fatw-%j.err

source /iridisfs/home/as17n23/.bashrc
conda activate fyp

# Set working directory and Python path to project root
cd /iridisfs/scratch/as17n23/Interactive-3D-Visualizer-for-Explainable-Telescope-Scheduling-in-TimeDomain-Astronomy-fatema
export PYTHONPATH="$PWD:$PYTHONPATH"

mkdir -p logs

python scripts/evaluation.py --maps 1000 --workers 24 --out results/results.csv

echo "Evaluation completed for FATW dataset."