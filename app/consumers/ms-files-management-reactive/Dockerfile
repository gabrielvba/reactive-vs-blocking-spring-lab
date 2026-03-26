# Stage 1: Build
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /app

# Copy pom.xml and download dependencies (cache layer)
COPY app/consumers/ms-files-management-reactive/pom.xml .
RUN mvn dependency:go-offline -B

# Copy source code and build
COPY app/consumers/ms-files-management-reactive/src ./src
RUN mvn clean package -DskipTests -B

# Stage 2: Runtime
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app

# Create non-root user for security
RUN addgroup -S spring \
  && adduser -S spring -G spring

# Copy JAR from build stage
COPY --from=build /app/target/*.jar app.jar

# Ensure application files are owned by the non-root user
RUN chown -R spring:spring /app

USER spring:spring

# Expose port
EXPOSE 8083

# Run the application
ENTRYPOINT ["java", "-jar", "app.jar"]

