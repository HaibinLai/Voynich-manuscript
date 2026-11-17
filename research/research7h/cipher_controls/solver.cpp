// Local substitution search. Inputs contain no plaintext key or target plaintext.
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <random>
#include <set>
#include <string>
#include <vector>
using namespace std;
struct Word { vector<int> letters; int count; };
int main(int argc,char**argv){
 if(argc!=8){cerr<<"model.bin ciphertext.txt frequency.txt mode restarts steps seed\n";return 2;}
 vector<double> model(27*27*27*27);ifstream mf(argv[1],ios::binary);mf.read((char*)model.data(),model.size()*sizeof(double));if(!mf){cerr<<"invalid model\n";return 3;}
 ifstream tf(argv[2]);map<string,int> counted;string word;array<long,26> cf{};
 while(tf>>word){for(char c:word){if(c<'a'||c>'z'){cerr<<"invalid cipher\n";return 4;}cf[c-'a']++;}counted[word]++;}
 vector<Word> words;array<vector<int>,26> postings;
 for(auto &item:counted){Word w;w.count=item.second;set<int> seen;for(char c:item.first){w.letters.push_back(c-'a');seen.insert(c-'a');}for(int c:seen)postings[c].push_back(words.size());words.push_back(w);}
 ifstream ff(argv[3]);array<double,26> pf{};for(double &v:pf)ff>>v;if(!ff){cerr<<"invalid frequencies\n";return 5;}
 bool bag=string(argv[4])=="bag";int restarts=stoi(argv[5]),steps=stoi(argv[6]);unsigned seed=stoul(argv[7]);mt19937 rng(seed);uniform_real_distribution<double> uniform(0,1);uniform_int_distribution<int>letter(0,25);
 array<int,26> ci,pi,initial; iota(ci.begin(),ci.end(),0);iota(pi.begin(),pi.end(),0);
 stable_sort(ci.begin(),ci.end(),[&](int a,int b){return cf[a]>cf[b];});stable_sort(pi.begin(),pi.end(),[&](int a,int b){return pf[a]>pf[b];});for(int i=0;i<26;i++)initial[ci[i]]=pi[i];
 auto ws=[&](int wi,const array<int,26>& key){const Word&w=words[wi];vector<int> v;v.reserve(w.letters.size());for(int c:w.letters)v.push_back(key[c]);if(bag)sort(v.begin(),v.end());int a=26,b=26,c=26;double s=0;for(int d:v){s+=model[((a*27+b)*27+c)*27+d];a=b;b=c;c=d;}s+=model[((a*27+b)*27+c)*27+26];return s*w.count;};
 double global=-1e300;array<int,26> best{};vector<double> scores;vector<int> accepted;auto start=chrono::steady_clock::now();
 for(int r=0;r<restarts;r++){
  array<int,26>key=initial;if(r>0){if(r>=restarts-2)shuffle(key.begin(),key.end(),rng);else for(int j=0;j<4+r*2;j++)swap(key[letter(rng)],key[letter(rng)]);}
  vector<double> cache(words.size());double total=0;for(int i=0;i<(int)words.size();i++)total+=(cache[i]=ws(i,key));double restartbest=total;int acc=0;vector<int>marks(words.size(),-1),affected;vector<double>newvalues;
  if(total>global){global=total;best=key;}
  for(int step=0;step<steps;step++){
   int x=letter(rng),y=letter(rng);if(x==y)continue;affected.clear();
   for(int i:postings[x]){marks[i]=step;affected.push_back(i);}for(int i:postings[y])if(marks[i]!=step)affected.push_back(i);
   swap(key[x],key[y]);newvalues.clear();double delta=0;for(int i:affected){double s=ws(i,key);newvalues.push_back(s);delta+=s-cache[i];}
   double temp=20.*pow(.01,double(step)/max(1,steps-1));
   if(delta>=0||uniform(rng)<exp(delta/temp)){total+=delta;acc++;for(int j=0;j<(int)affected.size();j++)cache[affected[j]]=newvalues[j];if(total>restartbest)restartbest=total;if(total>global){global=total;best=key;}}
   else swap(key[x],key[y]);
  }
  scores.push_back(restartbest);accepted.push_back(acc);
 }
 double checked=0;for(int i=0;i<(int)words.size();i++)checked+=ws(i,best);double seconds=chrono::duration<double>(chrono::steady_clock::now()-start).count();
 cout<<setprecision(17)<<"{\"mode\":\""<<(bag?"bag":"ordered")<<"\",\"seed\":"<<seed<<",\"restarts\":"<<restarts<<",\"steps\":"<<steps<<",\"mapping\":\"";for(int c:best)cout<<char('a'+c);
 cout<<"\",\"score\":"<<checked<<",\"accumulation_drift\":"<<global-checked<<",\"seconds\":"<<seconds<<",\"restart_scores\":[";
 for(int i=0;i<restarts;i++){if(i)cout<<",";cout<<scores[i];}cout<<"],\"accepted_swaps\":[";for(int i=0;i<restarts;i++){if(i)cout<<",";cout<<accepted[i];}cout<<"]}\n";
}
