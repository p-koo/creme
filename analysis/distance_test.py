import glob
import pickle
import pandas as pd
import seaborn as sns
import numpy as np
import matplotlib.pyplot as plt
import pyranges as pr
import sys, os, h5py
import kipoiseq
from tqdm import tqdm
import json
sys.path.append('../creme')
import creme
import custom_model
import utils
import glob


########################################################################################
# parameters
########################################################################################

def main():

    if len(sys.argv) == 4:
        model_name = sys.argv[1]
        num_shuffle = int(sys.argv[2])
        set_seed = bool(sys.argv[3])
    else:
        model_name = sys.argv[1]
        num_shuffle = int(sys.argv[2])
        set_seed = False

    perturb_window = 5000

    data_dir = '../data/'
    fasta_path = f'{data_dir}/GRCh38.primary_assembly.genome.fa'
    result_dir = utils.make_dir(f'../results/distance_test_{set_seed}')
    result_dir_model = utils.make_dir(f'{result_dir}/{model_name}_{num_shuffle}/')
    csv_dir = f'../results/summary_csvs/{model_name}/'
    print(f'USING model {model_name}')
    cre_df_path = f'{csv_dir}/sufficient_CREs.csv'

    if model_name.lower() == 'enformer':
        track_index = [4824, 5110, 5111]
        model = custom_model.Enformer(track_index=track_index)
        target_df = pd.read_csv(f'{data_dir}/enformer_targets_human.txt', sep='\t')
        cell_lines = [utils.clean_cell_name(target_df.iloc[t]['description']) for t in track_index]
        compute_mean = True
    elif model_name.lower() == 'borzoi':
        target_df = pd.read_csv('../data/borzoi_targets_human.txt', sep='\t')
        cell_lines_for_search = ['K562 ENCODE, biol_']
        cell_line_info, cage_tracks = utils.get_borzoi_targets(target_df, cell_lines_for_search)
        print('Loading Borzoi(s)')
        model = custom_model.Borzoi('../data/borzoi/*/*', track_index=cage_tracks, aggregate=True)
        model.bin_index = list(np.arange(model.target_lengths // 2 - 4, model.target_lengths // 2 + 4, 1))
        compute_mean = False
    else:
        print('Unkown model')
        sys.exit(1)


    # load CRE dataframe (with all CRE positions)
    cre_df = pd.read_csv(cre_df_path)


    # tile_coords = pd.read_csv(f'{csv_dir}/sufficiency_test_tile_coordinates.csv', index_col='Unnamed: 0').T
    # tss_tile = tile_coords.loc['tss'].T.values
    # cre_tile_coords = tile_coords.loc[[t for t in tile_coords.index if 'tss' not in t]]
    # cre_tiles_starts = cre_tile_coords[0].values
    tss_tile, cre_tiles = utils.set_tile_range(model.seq_length, perturb_window)
    cre_tiles_starts = np.array(cre_tiles)[:, 0]

    # set up sequence parser from fasta
    seq_parser = utils.SequenceParser(fasta_path)
    cre_df = cre_df.sample(frac=1)
    # loop through and predict TSS activity
    for i, row in tqdm(cre_df.iterrows(), total=len(cre_df)):
        tile_start, tile_end = [row['tile_start'], row['tile_end']]
        result_path = f'{result_dir_model}/{row["seq_id"]}_{tile_start}_{tile_end}.pickle'
        print(result_path)
        if not os.path.isfile(result_path):
            # get sequence from reference genome and convert to one-hot
            chrom, start, strand = row['seq_id'].split('_')[1:]
            x = seq_parser.extract_seq_centered(chrom, int(start), strand, model.seq_length, onehot=True)

            # perform TSS-CRE distance dependence Test

            res = creme.distance_test(model, x, tss_tile, [tile_start, tile_end],
                                       cre_tiles_starts, num_shuffle, mean=compute_mean,
                                       seed=set_seed)

            # store predictions
            utils.save_pickle(result_path, res)

if __name__ == '__main__':
    main()


