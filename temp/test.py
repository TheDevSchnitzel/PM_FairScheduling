# import the required libraries 
import random 
import matplotlib.pyplot as plt 
    
# store the random numbers in a list 
nums = [] 
mu = 1500
sigma = 50
    
for i in range(10000): 
    #temp = random.normalvariate(mu, sigma) 
    temp = random.uniform(16000000000, 16800000000)
    temp += random.weibullvariate(100000000, 500)
    nums.append(temp) 
        
# plotting a graph 
plt.hist(nums, bins = 200) 
plt.show()