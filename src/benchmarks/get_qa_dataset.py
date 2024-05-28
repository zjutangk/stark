import os.path as osp
from src.benchmarks.qa_datasets import AmazonSTaRKDataset, PrimeKGSTaRKDataset, MAGSTaRKDataset, STaRKDataset


def get_qa_dataset(name, root='data/', human_generated_eval=False):
    qa_root = osp.join(root, name)
    if name == 'amazon':
        split_dir = osp.join(qa_root, 'split')
        stark_qa_dir = osp.join(qa_root, 'stark_qa')
        dataset = AmazonSTaRKDataset(stark_qa_dir, split_dir, 
                                     human_generated_eval=human_generated_eval)
    elif name == 'primekg':
        split_dir = osp.join(qa_root, 'split')
        stark_qa_dir = osp.join(qa_root, 'stark_qa')
        dataset = PrimeKGSTaRKDataset(stark_qa_dir, split_dir, 
                                      human_generated_eval=human_generated_eval)
    elif name == 'mag':
        split_dir = osp.join(qa_root, 'split')
        stark_qa_dir = osp.join(qa_root, 'stark_qa')
        dataset = MAGSTaRKDataset(stark_qa_dir, split_dir, 
                                  human_generated_eval=human_generated_eval)
    else:
        try:
            print('loading dataset from external data')
            split_dir = osp.join(qa_root, 'split')
            stark_qa_dir = osp.join(qa_root, 'stark_qa')
            dataset = STaRKDataset(stark_qa_dir, split_dir)
        except Exception as e:
            print('Please check dataset name, path, or format\n')
            raise e
    return dataset
    
    