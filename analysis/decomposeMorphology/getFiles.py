import os
import sys
import numpy as np

if __name__ == "__main__":
    filesList = ['/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo5284_chromo5285.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo4078_chromo4079.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo1502_chromo1506.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo3494_chromo3495.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo4690_chromo4692.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo2145_chromo2146.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo4082_chromo4084.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo1514_chromo1518.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo1814_chromo1815.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo1522_chromo1526.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo4705_chromo4706.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo1815_chromo1816.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo2993_chromo2994.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo2152_chromo2153.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo5296_chromo5297.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo4707_chromo4708.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo3502_chromo3504.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo5300_chromo5301.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo4708_chromo4709.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo5301_chromo5303.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo5303_chromo5305.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo2998_chromo3000.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo5305_chromo5307.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo3001_chromo3002.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo5317_chromo5319.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo3002_chromo3003.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo5327_chromo5329.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo5331_chromo5333.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo5357_chromo5359.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo5391_chromo5395.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo5395_chromo5399.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo5403_chromo5407.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo5411_chromo5415.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo5419_chromo5421.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo5421_chromo5423.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo5425_chromo5427.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo5433_chromo5435.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo5435_chromo5437.inp', '/scratch/erjank_project/mattyMorphCT/outputFiles/p1-L15-f0.0-P0.1-T2.25-e0.5/chromophores/inputORCA/pair/chromo5457_chromo5461.inp']
    for fileName in filesList:
        os.system('scp kestrel:'+fileName+' ./brokenInps/')