-- CreateTable
CREATE TABLE "Vehicle" (
    "id" TEXT NOT NULL,
    "make" TEXT,
    "url" TEXT NOT NULL,
    "model" TEXT,
    "price" INTEGER NOT NULL,
    "profile_url" TEXT,
    "transmission" TEXT,
    "year" INTEGER NOT NULL,
    "city" TEXT NOT NULL,
    "color" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "description" VARCHAR(1000),
    "engine_size" TEXT,
    "fuel_type" TEXT,

    CONSTRAINT "Vehicle_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "FacebookImage" (
    "id" SERIAL NOT NULL,
    "url" TEXT NOT NULL,

    CONSTRAINT "FacebookImage_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "_FacebookImageToVehicle" (
    "A" INTEGER NOT NULL,
    "B" TEXT NOT NULL
);

-- CreateIndex
CREATE UNIQUE INDEX "Vehicle_id_key" ON "Vehicle"("id");

-- CreateIndex
CREATE UNIQUE INDEX "FacebookImage_url_key" ON "FacebookImage"("url");

-- CreateIndex
CREATE UNIQUE INDEX "_FacebookImageToVehicle_AB_unique" ON "_FacebookImageToVehicle"("A", "B");

-- CreateIndex
CREATE INDEX "_FacebookImageToVehicle_B_index" ON "_FacebookImageToVehicle"("B");

-- AddForeignKey
ALTER TABLE "_FacebookImageToVehicle" ADD CONSTRAINT "_FacebookImageToVehicle_A_fkey" FOREIGN KEY ("A") REFERENCES "FacebookImage"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "_FacebookImageToVehicle" ADD CONSTRAINT "_FacebookImageToVehicle_B_fkey" FOREIGN KEY ("B") REFERENCES "Vehicle"("id") ON DELETE CASCADE ON UPDATE CASCADE;
