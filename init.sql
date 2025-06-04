
-- 1) Tabla Beneficiario
DROP TABLE IF EXISTS beneficiario CASCADE;
CREATE TABLE beneficiario (
    rut            VARCHAR(20)   PRIMARY KEY,
    nombre         VARCHAR(100)  NOT NULL,
    tramo_ingreso  CHAR(1)       NOT NULL
);

-- 2) Tabla Medico (sin columna id_region)
DROP TABLE IF EXISTS medico CASCADE;
CREATE TABLE medico (
    rut            VARCHAR(20)   PRIMARY KEY,
    nombre         VARCHAR(100)  NOT NULL,
    especialidad   VARCHAR(100)  NOT NULL
);

-- 3) Tabla Bono (sin columna id_region)
DROP TABLE IF EXISTS bono CASCADE;
CREATE TABLE bono (
    id_bono          VARCHAR(20)   PRIMARY KEY,
    fecha_emision    DATE          NOT NULL,
    descripcion      TEXT          NULL,
    valor_total      DECIMAL(12,2) NOT NULL,
    valor_copago     DECIMAL(12,2) NOT NULL,
    valor_apagar     DECIMAL(12,2) NOT NULL,
    rut_beneficiario VARCHAR(20)   NOT NULL,
    rut_medico       VARCHAR(20)   NOT NULL,
    CONSTRAINT fk_bono_beneficiario
        FOREIGN KEY (rut_beneficiario)
        REFERENCES beneficiario(rut)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT fk_bono_medico
        FOREIGN KEY (rut_medico)
        REFERENCES medico(rut)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);