# https://stackoverflow.com/questions/39204142/docker-compose-with-multiple-database

CREATE DATABASE IF NOT EXISTS `superset`;
CREATE DATABASE IF NOT EXISTS `keep`;


-- Create or update the root user for remote connections
CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY 'keep';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%';

-- Make sure permissions are applied
FLUSH PRIVILEGES;
