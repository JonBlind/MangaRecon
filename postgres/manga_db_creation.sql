SET timezone TO 'UTC';

DROP TABLE IF EXISTS "user" CASCADE;
DROP TABLE IF EXISTS manga CASCADE;
DROP TABLE IF EXISTS author CASCADE;
DROP TABLE IF EXISTS genre CASCADE;
DROP TABLE IF EXISTS tag CASCADE;
DROP TABLE IF EXISTS demographic CASCADE;
DROP TABLE IF EXISTS rating CASCADE;
DROP TABLE IF EXISTS collection CASCADE;
DROP TABLE IF EXISTS manga_author CASCADE;
DROP TABLE IF EXISTS manga_collection CASCADE;
DROP TABLE IF EXISTS manga_genre CASCADE;
DROP TABLE IF EXISTS manga_tag CASCADE;
DROP TABLE IF EXISTS manga_demographic CASCADE;

CREATE TABLE "user" (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  email TEXT UNIQUE NOT NULL,
  hashed_password TEXT NOT NULL,
  username TEXT UNIQUE NOT NULL,
  displayname TEXT NOT NULL CHECK (LENGTH(displayname) <= 64),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  last_login TIMESTAMP WITH TIME ZONE,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
  is_verified BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE manga(
  manga_id INT NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1) PRIMARY KEY,
  title VARCHAR(255) NOT NULL UNIQUE,
  author_id INT NOT NULL,
  description TEXT,
  published_date DATE,
  external_average_rating NUMERIC(2,1) CHECK (external_average_rating >= 0 AND external_average_rating <= 5 AND (external_average_rating * 10) % 1 = 0),
  average_rating NUMERIC(2,1) CHECK (average_rating >= 0 AND average_rating <= 5 AND (average_rating * 10) % 1 = 0)
);

CREATE TABLE author(
  author_id INT NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1) PRIMARY KEY,
  author_name VARCHAR(255)
);

CREATE TABLE genre(
  genre_id INT NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1) PRIMARY KEY,
  genre_name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE tag(
  tag_id INT NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1) PRIMARY KEY,
  tag_name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE demographic(
  demographic_id INT NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1) PRIMARY KEY,
  demographic_name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE rating(
  user_id UUID NOT NULL,
  manga_id INT NOT NULL,
  personal_rating NUMERIC(3,1) CHECK (personal_rating >= 0 AND personal_rating <= 10 AND (personal_rating) % 0.5 = 0),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, manga_id),
  FOREIGN KEY (user_id) REFERENCES "user" (id) ON DELETE CASCADE,
  FOREIGN KEY (manga_id) REFERENCES manga (manga_id) ON DELETE CASCADE
);

CREATE TABLE collection(
  collection_id INT NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1) PRIMARY KEY,
  user_id UUID NOT NULL,
  collection_name VARCHAR(255) NOT NULL,
  description VARCHAR(255),
  is_public BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES "user" (id) ON DELETE CASCADE,
  CONSTRAINT unique_user_collection UNIQUE (user_id, collection_name)
);

CREATE TABLE manga_author(
  manga_id INT NOT NULL,
  author_id INT NOT NULL,
  FOREIGN KEY (manga_id) REFERENCES manga (manga_id) ON DELETE CASCADE,
  FOREIGN KEY (author_id) REFERENCES author (author_id) ON DELETE CASCADE,
  PRIMARY KEY (manga_id, author_id)
);

CREATE TABLE manga_collection(
  manga_id INT NOT NULL,
  collection_id INT NOT NULL,
  added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (manga_id, collection_id),
  FOREIGN KEY (manga_id) REFERENCES manga (manga_id) ON DELETE CASCADE,
  FOREIGN KEY (collection_id) REFERENCES collection (collection_id) ON DELETE CASCADE
);

CREATE TABLE manga_genre(
  manga_id INT NOT NULL,
  genre_id INT NOT NULL,
  FOREIGN KEY (manga_id) REFERENCES manga(manga_id) ON DELETE CASCADE,
  FOREIGN KEY (genre_id) REFERENCES genre(genre_id) ON DELETE CASCADE,
  PRIMARY KEY (manga_id, genre_id)
);

CREATE TABLE manga_tag(
  manga_id INT NOT NULL,
  tag_id INT NOT NULL,
  FOREIGN KEY (manga_id) REFERENCES manga(manga_id) ON DELETE CASCADE,
  FOREIGN KEY (tag_id) REFERENCES tag(tag_id) ON DELETE CASCADE,
  PRIMARY KEY (manga_id, tag_id)
);

CREATE TABLE manga_demographic(
  manga_id INT NOT NULL,
  demographic_id INT NOT NULL,
  FOREIGN KEY (manga_id) REFERENCES manga(manga_id) ON DELETE CASCADE,
  FOREIGN KEY (demographic_id) REFERENCES demographic(demographic_id) ON DELETE CASCADE,
  PRIMARY KEY (manga_id, demographic_id)
);

-- Indexes for the user table
CREATE UNIQUE INDEX idx_user_username ON "user" (LOWER(username));
CREATE UNIQUE INDEX idx_user_email ON "user" (LOWER(email));

-- Indexes for the manga table
CREATE INDEX idx_manga_title ON manga(title);
CREATE INDEX idx_manga_author ON manga(author_id);

-- Indexes for the rating table
CREATE INDEX idx_rating_user_id ON rating(user_id);
CREATE INDEX idx_rating_manga_id ON rating(manga_id);

-- Indexes for the collection table
CREATE INDEX idx_collection_user_id ON collection(user_id);
CREATE INDEX idx_collection_is_public ON collection(is_public);
