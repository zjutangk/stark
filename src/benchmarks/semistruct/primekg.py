import os
import os.path as osp
import pickle
import torch
import pandas as pd
import sys
from src.benchmarks.semistruct.knowledge_base import SemiStructureKB
from src.tools.process_text import compact_text, clean_dict
from src.tools.node import Node, register_node
from src.tools.io import save_files, load_files
from tdc.resource import PrimeKG
import json


class PrimeKGSemiStruct(SemiStructureKB):
    
    NODE_TYPES = ['disease', 'gene/protein', 'molecular_function', 'drug', 'pathway', 
                  'anatomy', 'effect/phenotype','biological_process', 'cellular_component', 'exposure']
    RELATION_TYPES = ['ppi', 'carrier', 'enzyme', 'target', 'transporter', 'contraindication', 
                      'indication', 'off-label use','synergistic interaction', 'associated with', 
                      'parent-child', 'phenotype absent', 'phenotype present', 'side effect',
                      'interacts with', 'linked to', 'expression present', 'expression absent']
    META_DATA = ['id', 'type', 'name', 'source', 'details']
    candidate_types = NODE_TYPES 

    def __init__(self, save_path=None, meta_path=None, kg_path=None, renew=False):
        '''
            Args: 
                save_path (Path or str): dir that stores processed data
                meta_path (Path or str): metadata path
        '''
        
        # construct the graph based on link info in the raw data
        self.raw_data = 'Not loaded'
        self.kg_path = kg_path
        self.renew = renew
        processed_data = self.process_raw(save_path, meta_path)
        super(PrimeKGSemiStruct, self).__init__(**processed_data)
        self.node_info = clean_dict(self.node_info)

        self.node_attr_dict = {}
        for node_type in self.node_type_lst():
            attrbutes = []
            for idx in self.get_node_ids_by_type(node_type):
                attrbutes.extend(self[idx].__attr__())
            self.node_attr_dict[node_type] = list(set(attrbutes))

    def process_raw(self, save_path, meta_path):
        if save_path is not None and osp.exists(osp.join(save_path, 'node_info.pkl')) and self.renew == False:
            files = load_files(save_path)
            print(f'Loaded from {save_path}!')
        else:
            if not osp.isdir(save_path):
                os.makedirs(save_path)
            print('Loading data... It might take a while')
            with open(self.kg_path, 'r') as rf:
                self.raw_data = pd.read_csv(rf)

            # Construct basic information for each node and edge
            node_info = {}
            node_type_dict = {}
            node_types= {}
            cnt_dict = {}
            ntypes = self.NODE_TYPES
            for idx, node_t in enumerate(ntypes):
                node_type_dict[idx] = node_t
                cnt_dict[node_t] = [0, 0, 0.]
                
            for idx, node_id, node_type, node_name, source in zip(self.raw_data['x_index'], self.raw_data['x_id'], 
                                                                  self.raw_data['x_type'], self.raw_data['x_name'], 
                                                                  self.raw_data['x_source']):
                if idx in node_info.keys(): 
                    continue
                node_info[idx] = {'id': node_id, 'type': node_type, 'name': node_name, 'source': source}
                node_types[idx] = ntypes.index(node_type)
                cnt_dict[node_type][0] += 1
                
            for idx, node_id, node_type, node_name, source in zip(self.raw_data['y_index'], self.raw_data['y_id'], 
                                                                  self.raw_data['y_type'], self.raw_data['y_name'], 
                                                                  self.raw_data['y_source']):
                if idx in node_info.keys(): 
                    continue
                
                node_info[idx] = {'id': node_id, 'type': node_type, 'name': node_name, 'source': source}
                node_types[idx] = ntypes.index(node_type)
                cnt_dict[node_type][0] += 1
                
            assert len(node_info) == max(node_types.keys()) + 1
            node_types = [node_types[idx] for idx in range(len(node_types))]

            edge_index = [[], []]
            edge_types = []
            edge_type_dict = {}
            rel_types = self.RELATION_TYPES
            for idx, edge_t in enumerate(rel_types):
                edge_type_dict[idx] = edge_t
            
            for head_id, tail_id, relation_type in zip(self.raw_data['x_index'], 
                                                       self.raw_data['y_index'], 
                                                       self.raw_data['display_relation']):
                edge_index[0].append(head_id)
                edge_index[1].append(tail_id)
                edge_types.append(rel_types.index(relation_type))
                if relation_type not in edge_type_dict.values():
                    print('unexpected new relation type', relation_type)
                    edge_type_dict[len(edge_type_dict)] = relation_type
                
            edge_index = torch.LongTensor(edge_index)
            edge_types = torch.LongTensor(edge_types)
            node_types = torch.LongTensor(node_types)

            # Construct meta information for nodes
            with open(meta_path, 'rb') as f:
                meta = pickle.load(f)
            
            pathway_dict = meta['pathway']
            pathway = {}
            for v in pathway_dict.values():
                try:
                    pathway[v['name'][0]] = v
                except:
                    pass
            
            print('Constructing meta data for nodes...')
            print('Total number of nodes:', len(node_info))
            for idx in node_info.keys():
                tp = node_info[idx]['type']

                if tp in ['disease', 'drug', 'exposure', 'anatomy', 'effect/phenotype']:
                    continue
                elif tp in ['biological_process', 'molecular_function', 'cellular_component']:
                    node_meta =  meta[tp].get(node_info[idx]['id'], 'No meta data')
                elif tp == 'gene/protein':
                    node_meta = meta[tp].get(node_info[idx]['name'], 'No meta data')
                elif tp == 'pathway':
                    node_meta = pathway.get(node_info[idx]['name'], 'No meta data')
                else:
                    print('Unexpected type:', tp)
                    raise NotImplementedError

                if isinstance(node_meta, dict):
                    filtered_node_meta = {k: v for k, v in node_meta.items() if v is not None and v != ['']}
                    if filtered_node_meta == {}:
                        continue
                    else:
                        node_info[idx]['details'] = filtered_node_meta
                        cnt_dict[tp][1] += 1
                elif node_meta == 'No meta data':
                    continue
                elif isinstance(node_meta, str):
                    try:
                        assert node_meta == node_info[idx]['name']
                    except:
                        print('Problematic:', node_meta, node_info[idx]['name'])
                else:
                    raise NotImplementedError
            
            data = PrimeKG(path = './data')

            drug_feature = data.get_features(feature_type = 'drug')
            disease_feature = data.get_features(feature_type = 'disease')

            drug_set = set()
            for i in range(len(drug_feature)):
                id = drug_feature.iloc[i]['node_index']
                if id in drug_set:
                    continue
                drug_set.add(id)
                cnt_dict['drug'][1] += 1
                details_dict = drug_feature.iloc[i].to_dict()
                del details_dict['node_index']
                node_info[id]['details'] = details_dict
            
            disease_set = set()
            for i in range(len(disease_feature)):
                id = disease_feature.iloc[i]['node_index']
                if id in disease_set:
                    continue
                disease_set.add(id)
                cnt_dict['disease'][1] += 1
                details_dict = disease_feature.iloc[i].to_dict()
                del details_dict['node_index']
                node_info[id]['details'] = details_dict
            
            for k, trip in cnt_dict.items():
                cnt_dict[k] = (trip[0], trip[1], trip[1] * 1.0 / trip[0])
            with open(osp.join(save_path, 'stats.json'), 'w') as df:
                json.dump(cnt_dict, df, indent=4)
            
            files = {'node_info': node_info, 
                     'edge_index': edge_index, 
                     'edge_types': edge_types,
                     'edge_type_dict': edge_type_dict,
                     'node_types': node_types,
                     'node_type_dict': node_type_dict}
            if save_path is not None:
                print(f'Saving to {save_path}...')
                save_files(save_path=save_path, **files)
        return files
    
    def __getitem__(self, idx):
        idx = int(idx)
        node_info = self.node_info[idx]
        node = Node()
        register_node(node, node_info)
        return node
    
    def get_doc_info(self, idx, 
                     add_rel=True, 
                     compact=False,
                     n_rel=-1) -> str:
        node = self[idx]
        node_info = self.node_info[idx]
        doc = f'- name: {node.name}\n'
        doc += f'- type: {node.type}\n'
        doc += f'- source: {node.source}\n'
        gene_protein_text_explain = {
            'name': 'gene name',
            'type_of_gene': 'gene types',
            'alias': 'other gene names',
            'other_names': 'extended other gene names',
            'genomic_pos': 'genomic position',
            'generif': 'PubMed text',
            'interpro': 'protein family and classification information',
            'summary': 'protein summary text'
        }

        feature_text = f'- details:\n'
        feature_cnt = 0
        if 'details' in node_info.keys():
            for key, value in node_info['details'].items():
                if str(value) in ['', 'nan'] or key.startswith('_') or '_id' in key: 
                    continue
                if node.type == 'gene/protein' and key in gene_protein_text_explain.keys():
                    if 'interpro' in key:
                        if isinstance(value, dict):
                            value = [value]
                        value = [v['desc'] for v in value]
                    if 'generif' in key:
                        value = '; '.join([v['text'] for v in value])
                        value = ' '.join(value.split(' ')[:50000])
                    if 'genomic_pos' in key:
                        if isinstance(value, list):
                            value = value[0]
                    feature_text += f'  - {key} ({gene_protein_text_explain[key]}): {value}\n'
                    feature_cnt += 1
                else:
                    feature_text += f'  - {key}: {value}\n'
                    feature_cnt += 1
        if feature_cnt == 0: feature_text = ''
        
        doc += feature_text

        if add_rel:
            doc += self.get_rel_info(idx, n_rel=n_rel)
        if compact: 
            doc = compact_text(doc)

        return doc

    def get_rel_info(self, idx, rel_types=None, n_rel=-1):
        doc = ''
        rel_types = self.rel_type_lst() if rel_types is None else rel_types
        for edge_t in rel_types:
            node_ids = torch.LongTensor(self.get_neighbor_nodes(idx, edge_t))
            if len(node_ids) == 0: 
                continue
            doc += f"\n  {edge_t.replace(' ', '_')}: " + "{"
            node_types = self.node_types[node_ids]

            for node_type in set(node_types.tolist()):
                neighbors = []
                doc += f'{self.node_type_dict[node_type]}: '
                node_ids_t = node_ids[node_types == node_type]
                if n_rel > 0:
                    node_ids_t = node_ids_t[torch.randperm(len(node_ids_t))[:n_rel]]
                for i in node_ids_t:
                    neighbors.append(f'{self[i].name}')
                neighbors = '(' + ', '.join(neighbors) + '),'
                doc += neighbors
            doc += '}'
        if len(doc): 
            doc = '- relations:\n' + doc
        return doc
    
'''
Usage:
    from primekg import PrimeKGSemiStruct
    save_path = '/dfs/project/kgrlm/data/primekg_processed_extended'
    metadata_path = '/dfs/project/kgrlm/data/primekg_raw/primekg_metadata_extended.pkl'
    kg_path = '/dfs/project/kgrlm/data/primekg_raw/kg.csv'
    dataset = PrimeKGSemiStruct(save_path, metadata_path, kg_path)
'''
