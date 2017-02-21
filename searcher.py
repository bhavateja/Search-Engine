import urllib2
import re
from bs4 import BeautifulSoup
from urlparse import urljoin
from pysqlite2 import dbapi2 as sqlite

class searcher:
    def __init__(self,dbname):
        self.con = sqlite.connect(dbname)

    def __del__(self):
        self.con.close()

    def getmatchrows(self,q):
        
        # Strings to build the query
        fieldlist='w0.urlid'
        tablelist=''
        clauselist=''
        wordids=[]
        
        # Split the words by spaces
        words=q.split(' ')
        tablenumber=0
        
        for word in words:
            # Get the word ID
            wordrow=self.con.execute("select rowid from wordlist where word='%s'" % word).fetchone( )
            if wordrow!=None:
                wordid=wordrow[0]
                wordids.append(wordid)
                if tablenumber>0:
                    tablelist+=','
                    clauselist+=' and '
                    clauselist+='w%d.urlid=w%d.urlid and ' % (tablenumber-1,tablenumber)
                fieldlist+=',w%d.location' % tablenumber
                tablelist+='wordlocation w%d' % tablenumber
                clauselist+='w%d.wordid=%d' % (tablenumber,wordid)
                tablenumber+=1
        
        # Create the query from the separate parts
        fullquery='select %s from %s where %s' % (fieldlist,tablelist,clauselist)
        cur=self.con.execute(fullquery)
        rows=[row for row in cur]
        return rows,wordids

    def getscoredlist(self,rows,wordids):
        totalscores=dict([(row[0],0) for row in rows])
        
        # This is where you'll later put the scoring functions
        #weights=[]
        #weights=[(1.0,self.frequencyscore(rows))]  ## Ferquency Score
        #weights=[(1.0,self.locationscore(rows))]   ## Location Score
        #weights=[(1.0,self.frequencyscore(rows)),(1.5,self.locationscore(rows))]   ## Combination of above
        
        weights=[(1.0,self.locationscore(rows)),(1.0,self.frequencyscore(rows)),(1.0,self.pagerankscore(rows))]
        
        for (weight,scores) in weights:
            for url in totalscores:
                totalscores[url]+=weight*scores[url]
        
        return totalscores

    def geturlname(self,id):
        return self.con.execute("select url from urllist where rowid=%d" % id).fetchone( )[0]


    def query(self,q):
        rows,wordids=self.getmatchrows(q)
        scores=self.getscoredlist(rows,wordids)
        rankedscores=sorted([(score,url) for (url,score) in scores.items( )],reverse=1)
        for (score,urlid) in rankedscores[0:10]:
            print '%f\t%s' % (score,self.geturlname(urlid))


    def normalizescores(self,scores,smallIsBetter=0):
        vsmall=0.00001 # Avoid division by zero errors
        if smallIsBetter:
            minscore=min(scores.values( ))
            return dict([(u,float(minscore)/max(vsmall,l)) for (u,l) in scores.items( )])
        else:
            maxscore=max(scores.values( ))
            if maxscore==0: maxscore=vsmall
            return dict([(u,float(c)/maxscore) for (u,c) in scores.items( )])

    
    def frequencyscore(self,rows):
        counts=dict([(row[0],0) for row in rows])
        for row in rows: counts[row[0]]+=1
        return self.normalizescores(counts)


    #Determines page relevance to a query is the search
    #terms location in the page. Usually, if a page is relevant to the search term, it will
    #appear closer to the top of the page
    def locationscore(self,rows):
        locations=dict([(row[0],1000000) for row in rows])
        for row in rows:
            loc=sum(row[1:])
            if loc<locations[row[0]]: locations[row[0]]=loc
        return self.normalizescores(locations,smallIsBetter=1)


    #Better to seek results in which the words in the query are close to each other in the page
    def distancescore(self,rows):
        # If there's only one word, everyone wins!
        if len(rows[0])<=2: return dict([(row[0],1.0) for row in rows])
        
        # Initialize the dictionary with large values
        mindistance=dict([(row[0],1000000) for row in rows])
        for row in rows:
            dist=sum([abs(row[i]-row[i-1]) for i in range(2,len(row))])
            if dist<mindistance[row[0]]: mindistance[row[0]]=dist
        
        return self.normalizescores(mindistance,smallIsBetter=1)

    def inboundlinkscore(self,rows):
        uniqueurls=set([row[0] for row in rows])
        inboundcount=dict([(u,self.con.execute('select count(*) from link where toid=%d' % u).fetchone( )[0]) for u in uniqueurls])
        return self.normalizescores(inboundcount)

    def pagerankscore(self,rows):
        pageranks=dict([(row[0],self.con.execute('select score from pagerank where urlid=%d' % row[0]).fetchone( )[0]) for row in rows])
        maxrank=max(pageranks.values( ))
        normalizedscores=dict([(u,float(l)/maxrank) for (u,l) in pageranks.items( )])
        return normalizedscores