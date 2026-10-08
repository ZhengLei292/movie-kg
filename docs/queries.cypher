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

// 6. 用户1对电影1的评分及时间
MATCH (s:MovieGraphState {key:'current'})
MATCH (u:MovieGraphUser {dataset:s.dataset,userId:1})-[r:RATED]->(m:MovieGraphMovie {dataset:s.dataset,movieId:1})
RETURN u,r,m;

// 7. 电影1评分人数、平均分与外部编号
MATCH (s:MovieGraphState {key:'current'})
MATCH (m:MovieGraphMovie {dataset:s.dataset,movieId:1})
RETURN m.movieId,m.title,m.ratingCount,m.averageRating,m.imdbId,m.tmdbId;

// 8. 用户1的共同高分邻居推荐：排除已评分候选，每个邻居只计一次
MATCH (s:MovieGraphState {key:'current'})
MATCH (u:MovieGraphUser {dataset:s.dataset,userId:1})-[ur:RATED]->(seed:MovieGraphMovie)
      <-[pr:RATED]-(peer:MovieGraphUser {dataset:s.dataset})
WHERE ur.rating>=4 AND pr.rating>=4 AND peer<>u AND seed.dataset=s.dataset
WITH DISTINCT u,peer,s
MATCH (peer)-[r:RATED]->(candidate:MovieGraphMovie {dataset:s.dataset})
WHERE r.rating>=4 AND NOT EXISTS { MATCH (u)-[:RATED]->(candidate) }
RETURN candidate.movieId,candidate.title,count(DISTINCT peer) AS supportingUsers,avg(r.rating) AS peerAverageRating
ORDER BY supportingUsers DESC,peerAverageRating DESC,candidate.movieId ASC LIMIT 5;
