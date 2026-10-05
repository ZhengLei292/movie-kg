// 1. 当前数据集
MATCH (s:MovieGraphState {key:'current'}) RETURN s.dataset;

// 2. 部分名称查询
MATCH (s:MovieGraphState {key:'current'})
MATCH (m:MovieGraphMovie {dataset:s.dataset})
WHERE toLower(m.title) CONTAINS 'toy story'
RETURN m.movieId, m.title ORDER BY m.movieId;

// 3. Toy Story 的局部事实
MATCH (s:MovieGraphState {key:'current'})
MATCH (m:MovieGraphMovie {dataset:s.dataset,movieId:1})-[r:IN_GENRE|HAS_TAG]->(f)
RETURN m,r,f;

// 4. 按共同类型与标签数获取 Top 5
MATCH (s:MovieGraphState {key:'current'})
MATCH (m:MovieGraphMovie {dataset:s.dataset,movieId:1})-[:IN_GENRE|HAS_TAG]->(f)
      <-[:IN_GENRE|HAS_TAG]-(n:MovieGraphMovie)
WHERE n.dataset=s.dataset AND n.movieId<>m.movieId
WITH n,collect(DISTINCT CASE WHEN f:MovieGraphGenre THEN f.name END) AS genres,
       collect(DISTINCT CASE WHEN f:MovieGraphTag THEN f.name END) AS tags
RETURN n.movieId,n.title,genres,tags,size(genres)+size(tags) AS score
ORDER BY score DESC,n.movieId ASC LIMIT 5;

// 5. 类型关联电影
MATCH (s:MovieGraphState {key:'current'})
MATCH (m:MovieGraphMovie {dataset:s.dataset})-[:IN_GENRE]->(g:MovieGraphGenre {name:'Animation'})
RETURN m.movieId,m.title ORDER BY m.movieId LIMIT 20;
