import crawler
import searcher

pages = ['https://www.codechef.com/']

C = crawler.crawler('codechef.db')
C.createindextables()

print "Crawling :: \n"
C.crawl(pages)

print "Ranking Pages :: \n"
C.calculatepagerank()

S = searcher.searcher('codechef.db')

searchQuery = 'Saturday'
S.query(searchQuery)